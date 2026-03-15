"""
CodeDebt Guardian — WebSocket Server
Real-time scan progress, AI streaming, live dashboard updates.
Uses Redis pub/sub as message bus for multi-instance fan-out.
"""

import asyncio
import json
import logging
from typing import Dict, Set

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections grouped by channel (scan_id, org_id, etc.)."""

    def __init__(self):
        self._channels: Dict[str, Set[WebSocket]] = {}
        self._redis: aioredis.Redis = None
        self._pubsub_task: asyncio.Task = None

    async def start(self):
        """Start the Redis pub/sub listener."""
        self._redis = aioredis.from_url(settings.REDIS_URL)
        self._pubsub_task = asyncio.create_task(self._redis_listener())
        logger.info("WebSocket manager started with Redis pub/sub")

    async def stop(self):
        """Stop the Redis listener."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._redis:
            await self._redis.close()

    async def subscribe(self, channel: str, websocket: WebSocket):
        """Subscribe a WebSocket to a channel."""
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)
        logger.info(f"WebSocket subscribed to {channel} ({len(self._channels[channel])} clients)")

    async def unsubscribe(self, channel: str, websocket: WebSocket):
        """Remove a WebSocket from a channel."""
        if channel in self._channels:
            self._channels[channel].discard(websocket)
            if not self._channels[channel]:
                del self._channels[channel]

    async def broadcast(self, channel: str, message: str):
        """Send message to all WebSockets on a channel."""
        if channel not in self._channels:
            return
        disconnected = set()
        for ws in self._channels[channel]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            self._channels[channel].discard(ws)

    async def _redis_listener(self):
        """Listen for Redis pub/sub messages and relay to WebSocket clients."""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe("scan:*", "dashboard:*", "ai:*")

            async for message in pubsub.listen():
                if message["type"] in ("pmessage",):
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode()
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    await self.broadcast(channel, data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis listener error: {e}", exc_info=True)


manager = ConnectionManager()


def _verify_ws_token(token: str) -> dict:
    """Verify JWT token for WebSocket connections."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return {}


@router.websocket("/ws/scan/{scan_id}")
async def scan_websocket(
    websocket: WebSocket,
    scan_id: str,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time scan progress.
    Clients connect with ?token=<jwt> for authentication.
    """
    # Authenticate BEFORE accepting the connection
    if not token:
        await websocket.close(code=4401, reason="Authentication required")
        return

    user_payload = _verify_ws_token(token)
    if not user_payload:
        await websocket.close(code=4403, reason="Invalid token")
        return

    await websocket.accept()
    channel = f"scan:{scan_id}"

    try:
        await manager.subscribe(channel, websocket)
        await websocket.send_text(json.dumps({
            "type": "connected",
            "channel": channel,
            "scan_id": scan_id,
        }))

        # Keep connection alive with heartbeat
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle client messages (e.g., ping)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text(json.dumps({"type": "heartbeat"}))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from {channel}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.unsubscribe(channel, websocket)


@router.websocket("/ws/dashboard/{org_id}")
async def dashboard_websocket(
    websocket: WebSocket,
    org_id: str,
    token: str = Query(default=""),
):
    """WebSocket for live dashboard updates (org-scoped)."""
    user_payload = _verify_ws_token(token)
    if not user_payload:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()
    channel = f"dashboard:{org_id}"

    try:
        await manager.subscribe(channel, websocket)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unsubscribe(channel, websocket)

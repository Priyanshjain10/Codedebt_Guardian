"""
CodeDebt Guardian — API Gateway (v2)
Production-grade FastAPI application with auth, rate limiting, WebSocket, and CORS.
"""

import logging
import asyncio
import json
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from utils.logger import setup_structured_logging
from config import settings
from api.middleware import (
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlerMiddleware,
)
from api.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    register_user,
    login_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from database import get_db, init_db, close_db
from services.audit import log_action

from api.rate_limit import limiter

from api.routes.scans import router as scans_router
from api.routes.organizations import router as orgs_router
from api.routes.projects import router as projects_router
from api.routes.billing import router as billing_router
from api.routes.api_keys import router as api_keys_router
from api.routes.search import router as search_router
from api.routes.github import router as github_router
from api.routes.analytics import router as analytics_router
from api.websocket import router as ws_router

# Configure logging early
setup_structured_logging()
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database tables (dev convenience)
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")

    # Start WebSocket manager
    try:
        from api.websocket import manager

        await manager.start()
    except Exception as e:
        logger.warning(f"WebSocket manager start failed: {e}")

    yield

    # Shutdown
    try:
        from api.websocket import manager

        await manager.stop()
    except Exception:
        pass
    await close_db()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CodeDebt Guardian API",
    description="AI-Powered Technical Debt Detection & Remediation Platform",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Rate limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware stack (order matters — outermost first)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount route modules ──────────────────────────────────────────────────

app.include_router(scans_router)
app.include_router(orgs_router)
app.include_router(projects_router)
app.include_router(billing_router)
app.include_router(api_keys_router)
app.include_router(search_router)
app.include_router(github_router)
app.include_router(analytics_router)
app.include_router(ws_router)


# Legacy webhook router (GitHub App Debt Gate)
try:
    from api.webhook import router as webhook_router

    app.include_router(webhook_router)
except Exception:
    logger.warning("Webhook router not loaded")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/")
async def root():
    return {
        "service": "CodeDebt Guardian API",
        "status": "running",
        "docs": "/api/docs"
    }

@app.get("/health/live")
async def health_live():
    """Liveness probe indicating the HTTP server is running."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe verifying database, redis, and worker health."""
    checks = {"api": "ready"}
    status = "ready"

    # Database
    try:
        from database import async_engine
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ready"
    except Exception as e:
        status = "not_ready"
        checks["database"] = f"unreachable: {str(e)}"

    # Redis
    try:
        import redis

        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        checks["redis"] = "ready"
    except Exception as e:
        status = "not_ready"
        checks["redis"] = f"unreachable: {str(e)}"

    # Celery
    try:
        from workers.celery_app import celery_app

        res = celery_app.control.ping(timeout=2)
        if not res:
            status = "not_ready"
            checks["celery"] = "no workers available"
        else:
            checks["celery"] = "ready"
    except Exception as e:
        status = "not_ready"
        checks["celery"] = f"unreachable: {str(e)}"

    if status != "ready":
        raise HTTPException(status_code=503, detail=checks)

    return {"status": status, "checks": checks}


# ── Auth Endpoints ───────────────────────────────────────────────────────


@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db=Depends(get_db)):
    """Register a new user. Creates a default org + team automatically."""
    user, org = await register_user(req, db)
    await log_action(db, org.id, user.id, "user.registered", {"email": req.email})
    access = create_access_token(str(user.id), str(org.id))
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db=Depends(get_db)):
    """Login with email and password."""
    user, org_id = await login_user(req, db)
    if org_id:
        from uuid import UUID as _UUID

        await log_action(db, _UUID(org_id), user.id, "user.login", {"email": req.email})
    access = create_access_token(str(user.id), org_id)
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, db=Depends(get_db)):
    """Refresh an expired access token."""
    body = await request.json()
    token = body.get("refresh_token", "")
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.get("/api/v1/auth/me")
async def get_me(user=Depends(get_current_user)):
    """Get current authenticated user profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }


# ── Legacy Streaming Endpoint (backward compat) ─────────────────────────


class LegacyAnalyzeRequest(BaseModel):
    repo_url: str
    auto_fix: bool = False
    max_prs: int = 3


@app.post("/analyze")
@limiter.limit(settings.RATE_LIMIT_SCAN)
async def legacy_analyze(request: Request, req: LegacyAnalyzeRequest):
    """
    Legacy streaming analysis endpoint (backward compatible).
    Streams NDJSON progress events for the old vanilla JS frontend.
    """
    if not req.repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported")

    async def event_generator():
        try:
            from agents.orchestrator import CodeDebtOrchestrator

            orchestrator = CodeDebtOrchestrator(use_persistent_memory=True)

            gen = orchestrator.run_full_analysis_stream(repo_url=req.repo_url)
            for event in await asyncio.to_thread(list, gen):
                yield event
        except Exception as e:
            import traceback

            traceback.print_exc()
            yield (
                json.dumps({"status": "error", "message": f"Analysis failed: {str(e)}"})
                + "\n"
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Legacy Report Endpoint ───────────────────────────────────────────────


class LegacyReportRequest(BaseModel):
    repo_url: str
    scan_id: Optional[str] = None


@app.post("/report")
async def legacy_report(req: LegacyReportRequest):
    """Legacy CTO report generation endpoint."""
    from agents.orchestrator import CodeDebtOrchestrator
    from tools.cto_report import CTOReportGenerator

    analysis_data = None
    if req.scan_id:
        analysis_data = CodeDebtOrchestrator.load_scan_cache(req.scan_id)

    if not analysis_data:
        raise HTTPException(status_code=400, detail="No analysis data found")

    try:
        html = CTOReportGenerator().generate(analysis_data, repo_url=req.repo_url)
        return {"html": html}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Report generation failed: {str(e)}"
        )


# ── AI Gateway Health ────────────────────────────────────────────────────


@app.get("/api/v1/ai/health")
async def ai_health():
    """Check AI provider availability."""
    try:
        from services.ai_gateway import ai_gateway

        return {"providers": ai_gateway.health()}
    except Exception as e:
        return {"providers": {}, "error": str(e)}

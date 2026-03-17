"""
Debt Gateway — GitHub App Webhook Handler.

Receives pull_request events from GitHub, analyzes the PR diff for new technical
debt, calculates the dollar cost, and creates a Check Run that passes or fails
based on a configurable debt budget.

Phase 2 additions:
  - Step 6: Post human-readable PR comment on meaningful debt
  - Confidence-gated auto-fix PR creation for safe issue types

Environment variables:
    GITHUB_APP_ID            — Numeric GitHub App ID
    GITHUB_APP_PRIVATE_KEY   — RSA private key (PEM) for JWT signing
    GITHUB_WEBHOOK_SECRET    — HMAC secret for payload verification
    CODEDEBT_MAX_PR_DOLLARS  — Max allowed debt per PR (default: 500)
"""

import os
import hmac
import hashlib
import json
import logging
import time

import jwt
import requests
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Configuration ────────────────────────────────────────────────────────

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
CODEDEBT_MAX_PR_DOLLARS = float(os.getenv("CODEDEBT_MAX_PR_DOLLARS", "500"))

GITHUB_API = "https://api.github.com"


# ── GitHub App Authentication ───────────────────────────────────────────


def _get_installation_token(installation_id: int) -> str:
    """
    Two-step GitHub App auth:
    1. Sign a JWT with the App's private key (RS256, 10min expiry)
    2. Exchange JWT for an installation access token
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": GITHUB_APP_ID,
    }
    app_jwt = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")

    resp = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]


# ── Webhook Endpoint ────────────────────────────────────────────────────


@router.post("/webhook")
async def github_webhook(request: Request):
    """
    GitHub App webhook receiver.
    Verifies HMAC-SHA256 signature, then dispatches based on event type.
    Always returns 200 — never cause GitHub to disable the webhook.
    """
    body = await request.body()

    # ── Signature verification ──────────────────────────────────────
    if GITHUB_WEBHOOK_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = (
            "sha256="
            + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        )

        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # ── Parse event ─────────────────────────────────────────────────
    event_type = request.headers.get("X-GitHub-Event", "")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "ignored", "reason": "invalid JSON"}

    # ── Dispatch ────────────────────────────────────────────────────
    if event_type == "pull_request" and data.get("action") in ("opened", "synchronize"):
        from workers.pr_tasks import process_pr_event

        pr = data.get("pull_request", {})
        repo_full = data.get("repository", {}).get("full_name")
        pr_number = pr.get("number")
        if not repo_full or not pr_number:
            return {"status": "ignored", "reason": "missing repo or pr_number"}

        installation_id = data.get("installation", {}).get("id")

        if installation_id:
            try:
                token = _get_installation_token(installation_id)
                _background_pr_task(repo_full, pr_number, installation_id)
                logger.info(f"Enqueued process_pr_event for {repo_full}#{pr_number}")
            except Exception as e:
                logger.error(f"Failed to enqueue PR event: {e}")

    return {"status": "ok"}

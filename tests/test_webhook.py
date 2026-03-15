"""
Tests for the Debt Gateway webhook handler.
"""
import hmac
import hashlib
import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_signature(body: bytes, secret: str) -> str:
    """Compute the correct HMAC-SHA256 signature for a webhook payload."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _get_test_client(webhook_secret: str = "test_secret"):
    """Create a fresh FastAPI TestClient with the webhook router mounted."""
    # Patch env before importing to ensure config is picked up
    with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": webhook_secret}):
        # Re-import to pick up fresh env
        import importlib
        import api.webhook as wh_mod
        importlib.reload(wh_mod)

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(wh_mod.router)
        return TestClient(app), webhook_secret


# ── Tests ────────────────────────────────────────────────────────────────

class TestWebhookSignature:
    """Test HMAC-SHA256 signature verification."""

    def test_webhook_rejects_invalid_signature(self):
        """A request with a wrong signature must receive 401."""
        client, secret = _get_test_client("test_secret_reject")

        body = json.dumps({"action": "opened"}).encode()
        wrong_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        response = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": wrong_sig,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_webhook_accepts_valid_signature(self):
        """A request with the correct HMAC signature must receive 200."""
        client, secret = _get_test_client("test_secret_accept")

        body = json.dumps({"action": "ping"}).encode()
        valid_sig = _make_signature(body, secret)

        response = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": valid_sig,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200


class TestDiffParser:
    """Test the unified diff line extractor."""

    def test_extract_added_lines(self):
        """extract_added_lines should return only '+' lines, stripped of the prefix."""
        from workers.pr_tasks import extract_added_lines

        patch = (
            "@@ -10,6 +10,8 @@\n"
            " unchanged line\n"
            "-removed line\n"
            "+added line one\n"
            "+added line two\n"
            " another unchanged\n"
            "--- a/file.py\n"
            "+++ b/file.py\n"
            "+added after header\n"
        )

        result = extract_added_lines(patch)
        lines = result.strip().split("\n")

        assert "added line one" in lines
        assert "added line two" in lines
        assert "added after header" in lines
        assert "removed line" not in result
        assert "unchanged line" not in result
        # +++ header lines must NOT appear in output
        assert "++ b/file.py" not in result

import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt

from api.routes import billing as billing_routes
from api.routes import scans as scans_routes
from api import websocket as websocket_routes


class _ScalarListResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _ScalarOneResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


def _install_fake_stripe(monkeypatch, create_fn):
    fake_checkout = SimpleNamespace(Session=SimpleNamespace(create=create_fn))
    fake_stripe = SimpleNamespace(checkout=fake_checkout, api_key=None)
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)


def _configure_billing_settings(monkeypatch):
    monkeypatch.setattr(billing_routes.settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(billing_routes.settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(billing_routes.settings, "CORS_ORIGINS", ["http://localhost:3000"])
    monkeypatch.setattr(
        billing_routes.settings, "STRIPE_PRICE_PRO_MONTHLY", "price_pro_test"
    )
    monkeypatch.setattr(
        billing_routes.settings,
        "STRIPE_PRICE_ENTERPRISE_MONTHLY",
        "price_enterprise_test",
    )


@pytest.mark.asyncio
async def test_billing_checkout_requires_org_selection_for_multi_org(monkeypatch):
    _configure_billing_settings(monkeypatch)
    _install_fake_stripe(monkeypatch, lambda **_: SimpleNamespace(url="unused"))

    team_1 = uuid.uuid4()
    team_2 = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarListResult(
                [SimpleNamespace(team_id=team_1), SimpleNamespace(team_id=team_2)]
            ),
            _ScalarListResult(
                [
                    SimpleNamespace(org_id=uuid.uuid4()),
                    SimpleNamespace(org_id=uuid.uuid4()),
                ]
            ),
        ]
    )

    with pytest.raises(HTTPException, match="Multiple organizations found"):
        await billing_routes.create_checkout_session(
            billing_routes.CheckoutRequest(plan="pro"),
            user=SimpleNamespace(id=uuid.uuid4()),
            db=db,
        )


@pytest.mark.asyncio
async def test_billing_checkout_accepts_explicit_org_for_multi_org(monkeypatch):
    _configure_billing_settings(monkeypatch)
    captured = {}

    def _create_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.test/session")

    _install_fake_stripe(monkeypatch, _create_session)

    requested_org = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarListResult(
                [SimpleNamespace(team_id=uuid.uuid4()), SimpleNamespace(team_id=uuid.uuid4())]
            ),
            _ScalarOneResult(SimpleNamespace(org_id=requested_org)),
        ]
    )
    user_id = uuid.uuid4()
    result = await billing_routes.create_checkout_session(
        billing_routes.CheckoutRequest(plan="pro", org_id=str(requested_org)),
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result["checkout_url"] == "https://checkout.test/session"
    assert captured["metadata"]["org_id"] == str(requested_org)
    assert captured["metadata"]["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_legacy_scan_access_denied_for_other_users():
    scan = SimpleNamespace(project_id=None, triggered_by=uuid.uuid4())
    with pytest.raises(HTTPException, match="Access denied"):
        await scans_routes._authorize_scan_read_access(
            scan=scan,
            user=SimpleNamespace(id=uuid.uuid4()),
            db=MagicMock(),
        )


@pytest.mark.asyncio
async def test_legacy_scan_access_allowed_for_owner():
    user_id = uuid.uuid4()
    scan = SimpleNamespace(project_id=None, triggered_by=user_id)
    await scans_routes._authorize_scan_read_access(
        scan=scan,
        user=SimpleNamespace(id=user_id),
        db=MagicMock(),
    )


class _FakeWebSocket:
    def __init__(self):
        self.close = AsyncMock()
        self.accept = AsyncMock()


@pytest.mark.asyncio
async def test_scan_websocket_rejects_missing_token():
    ws = _FakeWebSocket()
    await websocket_routes.scan_websocket(ws, str(uuid.uuid4()), token="")
    ws.close.assert_awaited_once_with(code=4401, reason="Authentication required")


@pytest.mark.asyncio
async def test_scan_websocket_rejects_invalid_token():
    ws = _FakeWebSocket()
    await websocket_routes.scan_websocket(ws, str(uuid.uuid4()), token="bad-token")
    ws.close.assert_awaited_once_with(code=4403, reason="Invalid token")


def test_verify_ws_token_accepts_valid_token(monkeypatch):
    monkeypatch.setattr(websocket_routes.settings, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(websocket_routes.settings, "JWT_ALGORITHM", "HS256")
    token = jwt.encode({"sub": str(uuid.uuid4())}, "test-secret", algorithm="HS256")
    payload = websocket_routes._verify_ws_token(token)
    assert payload.get("sub")

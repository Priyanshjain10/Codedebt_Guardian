import json
import logging
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from utils.logger import setup_structured_logging
from api.main import app


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient):
    """Test standard liveness probe."""
    res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_health_ready(client: AsyncClient):
    """Test readiness probe components."""
    res = await client.get("/health/ready")

    # In test environment, redis/celery might be missing so expect 503.
    # Either way the response should have the correct structure.
    if res.status_code == 200:
        data = res.json()
        assert data["status"] == "ready"
        assert "checks" in data
    else:
        assert res.status_code == 503
        data = res.json()
        # FastAPI wraps HTTPException detail
        detail = data.get("detail", data)
        assert "database" in detail or "redis" in detail or "celery" in detail


@pytest.mark.asyncio
async def test_rate_limit_unauthenticated(client: AsyncClient):
    """Test that public scan requests are rate limited to 5/minute."""
    results = []
    for _ in range(7):
        res = await client.post(
            "/api/v1/scans", json={"repo_url": "https://github.com/test/repo"}
        )
        results.append(res.status_code)

    # At least one of the later requests should be 429
    assert 429 in results, f"Expected at least one 429 response, got: {results}"


def test_structured_json_logging(capsys):
    """Test that the central logger setup correctly emits JSON."""
    setup_structured_logging(level=logging.INFO)
    logger = logging.getLogger("test_structured")

    # Log a message
    logger.info("Test message", extra={"custom_field": "123"})

    # Capture standard output
    captured = capsys.readouterr()
    log_line = captured.out.strip().split("\\n")[-1]

    # Parse JSON
    data = json.loads(log_line)

    # Verify standard fields
    assert "timestamp" in data
    assert "level" in data
    assert data["level"] == "INFO"
    assert data["name"] == "test_structured"
    assert data["message"] == "Test message"

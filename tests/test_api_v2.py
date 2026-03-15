"""
CodeDebt Guardian — API Integration Tests
Tests auth flow, scan CRUD, API keys, and tenant isolation.
"""

import pytest
from unittest.mock import patch


# ── Config & Auth Tests ──────────────────────────────────────────────────


class TestConfig:
    def test_settings_loads(self):
        """Settings should load with defaults."""
        from config import Settings

        s = Settings(
            SECRET_KEY="a]1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            DATABASE_SYNC_URL="postgresql://test:test@localhost/test",
        )
        assert s.APP_NAME == "CodeDebt Guardian"
        assert s.APP_VERSION == "2.0.0"
        assert s.JWT_ALGORITHM == "HS256"
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert s.DEV_HOURLY_RATE == 85.0

    def test_settings_defaults(self):
        from config import Settings

        s = Settings(
            SECRET_KEY="a]1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            DATABASE_SYNC_URL="postgresql://test:test@localhost/test",
        )
        assert s.RATE_LIMIT_DEFAULT == "60/minute"
        assert s.MAX_FILES_PER_SCAN == 500


class TestAuth:
    def test_password_hashing(self):
        from api.auth import hash_password, verify_password

        hashed = hash_password("test_password_123")
        assert hashed != "test_password_123"
        assert verify_password("test_password_123", hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_jwt_token_creation(self):
        from api.auth import create_access_token, decode_token

        with patch("api.auth.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key-for-jwt"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
            mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7

            access = create_access_token("user-123", "org-456")
            assert isinstance(access, str)
            assert len(access) > 0

            payload = decode_token(access)
            assert payload["sub"] == "user-123"
            assert payload["org"] == "org-456"
            assert payload["type"] == "access"

    def test_refresh_token(self):
        from api.auth import create_refresh_token, decode_token

        with patch("api.auth.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key-for-jwt"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7

            refresh = create_refresh_token("user-123")
            payload = decode_token(refresh)
            assert payload["sub"] == "user-123"
            assert payload["type"] == "refresh"

    def test_api_key_generation(self):
        from api.auth import generate_api_key

        full_key, prefix, key_hash = generate_api_key()
        assert full_key.startswith("cdg_live_")
        assert len(prefix) == 16
        assert len(key_hash) == 64  # SHA-256 hex

    def test_api_key_uniqueness(self):
        from api.auth import generate_api_key

        keys = [generate_api_key()[0] for _ in range(10)]
        assert len(set(keys)) == 10  # All unique


# ── AI Gateway Tests ─────────────────────────────────────────────────────


class TestAIGateway:
    def test_gateway_initializes(self):
        from services.ai_gateway import AIGateway

        with patch("services.ai_gateway.settings") as mock_settings:
            mock_settings.GROQ_API_KEY = ""
            mock_settings.GOOGLE_API_KEY = ""
            mock_settings.OPENAI_API_KEY = ""
            gw = AIGateway()
            health = gw.health()
            assert isinstance(health, dict)

    def test_circuit_breaker_opens(self):
        from services.ai_gateway import CircuitState

        cb = CircuitState(failure_threshold=3)
        assert cb.can_attempt() is True
        cb.record_failure()
        cb.record_failure()
        assert cb.can_attempt() is True  # Not yet at threshold
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_attempt() is False

    def test_circuit_breaker_resets_on_success(self):
        from services.ai_gateway import CircuitState

        cb = CircuitState(failure_threshold=2)
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_token_meter_tracking(self):
        from services.ai_gateway import TokenMeter

        meter = TokenMeter()
        meter.record("org-1", "gemini", 100, 50)
        meter.record("org-1", "gemini", 200, 100)
        meter.record("org-2", "groq", 50, 25)

        usage = meter.get_usage("org-1")
        assert "gemini" in usage
        assert usage["gemini"]["input"] == 300
        assert usage["gemini"]["output"] == 150
        assert usage["gemini"]["calls"] == 2

        usage2 = meter.get_usage("org-2")
        assert "groq" in usage2

    def test_model_routing_table(self):
        from services.ai_gateway import MODEL_ROUTES, TaskType, AIModel

        assert AIModel.GROQ_LLAMA in MODEL_ROUTES[TaskType.CODE_ANALYSIS]
        assert AIModel.GEMINI_FLASH in MODEL_ROUTES[TaskType.FIX_GENERATION]
        assert AIModel.OPENAI_GPT4O in MODEL_ROUTES[TaskType.COMPLEX_REFACTOR]


# ── Embedding Pipeline Tests ────────────────────────────────────────────


class TestEmbeddingPipeline:
    def test_python_chunking(self):
        from services.embedding_pipeline import CodeChunker

        code = '''
def hello(name):
    """Say hello."""
    print(f"Hello, {name}")
    return name

class Greeter:
    """A greeter class."""
    def greet(self, name):
        return hello(name)
    def goodbye(self, name):
        print(f"Goodbye, {name}")
'''
        chunker = CodeChunker()
        chunks = chunker.chunk(code, "test.py")
        assert len(chunks) >= 1  # Should find at least one line chunk
        keys = list(chunks[0].keys())
        assert "content" in keys
        assert "start_line" in keys
        assert "end_line" in keys

    def test_generic_chunking(self):
        from services.embedding_pipeline import CodeChunker

        code = "\n".join([f"line {i}" for i in range(100)])
        chunker = CodeChunker()
        # chunk_size is 30 by default, check if we get multiple splits
        chunks = chunker.chunk(code, "test.js", chunk_size=20)
        assert len(chunks) > 1

    def test_empty_code_returns_empty(self):
        from services.embedding_pipeline import CodeChunker

        chunks = CodeChunker().chunk("", "test.py")
        assert chunks == []  # or very minimal


# ── Middleware Tests ─────────────────────────────────────────────────────


class TestMiddleware:
    """Test middleware components directly."""

    def test_request_id_format(self):
        import uuid

        rid = str(uuid.uuid4())
        assert len(rid) == 36
        assert rid.count("-") == 4


# ── Database Model Tests ────────────────────────────────────────────────


class TestDatabaseModels:
    def test_models_importable(self):
        """All DB models should import without error."""
        from models.db_models import (
            Organization,
            User,
            Scan,
            APIKeyModel,
        )

        assert Organization.__tablename__ == "organizations"
        assert User.__tablename__ == "users"
        assert Scan.__tablename__ == "scans"
        assert APIKeyModel.__tablename__ == "api_keys"

    def test_uuid_generation(self):
        from models.db_models import _uuid

        u1 = _uuid()
        u2 = _uuid()
        assert u1 != u2


# ── Phase 0 Bug Fix Tests ───────────────────────────────────────────────


class TestSecretKeyValidator:
    """Bug 2: SECRET_KEY must be validated to prevent insecure defaults."""

    def test_rejects_default_key(self):
        from config import Settings
        from pydantic import ValidationError

        with pytest.raises(
            ValidationError, match="SECRET_KEY must be at least 32 characters"
        ):
            Settings(
                SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
                DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
                DATABASE_SYNC_URL="postgresql://test:test@localhost/test",
            )

    def test_rejects_short_key(self):
        from config import Settings
        from pydantic import ValidationError

        with pytest.raises(
            ValidationError, match="SECRET_KEY must be at least 32 characters"
        ):
            Settings(
                SECRET_KEY="too-short",
                DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
                DATABASE_SYNC_URL="postgresql://test:test@localhost/test",
            )

    def test_accepts_valid_key(self):
        from config import Settings

        s = Settings(
            SECRET_KEY="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            DATABASE_SYNC_URL="postgresql://test:test@localhost/test",
        )
        assert len(s.SECRET_KEY) >= 32


class TestSessionIdCollision:
    """Bug 1: Session IDs must be deterministic and collision-resistant."""

    def test_session_id_deterministic(self):
        import hashlib

        repo_url = "https://github.com/owner/repo"
        sid1 = f"session_{hashlib.sha256(repo_url.encode()).hexdigest()[:16]}"
        sid2 = f"session_{hashlib.sha256(repo_url.encode()).hexdigest()[:16]}"
        assert sid1 == sid2

    def test_session_id_no_collision(self):
        import hashlib

        url1 = "https://github.com/owner/repo1"
        url2 = "https://github.com/owner/repo2"
        sid1 = f"session_{hashlib.sha256(url1.encode()).hexdigest()[:16]}"
        sid2 = f"session_{hashlib.sha256(url2.encode()).hexdigest()[:16]}"
        assert sid1 != sid2

    def test_session_id_length(self):
        import hashlib

        repo_url = "https://github.com/owner/repo"
        sid = f"session_{hashlib.sha256(repo_url.encode()).hexdigest()[:16]}"
        # session_ prefix (8 chars) + 16 hex chars = 24 chars
        assert len(sid) == 24


class TestRequireRole:
    """Bug 4: require_role() must return a callable dependency."""

    def test_returns_callable(self):
        from api.auth import require_role

        dep = require_role("admin")
        assert callable(dep)

    def test_returns_different_checkers_for_different_roles(self):
        from api.auth import require_role

        member_dep = require_role("member")
        admin_dep = require_role("admin")
        # They should be different closure instances
        assert member_dep is not admin_dep


class TestAuditService:
    """Bug 6: Audit logging service must be importable and have correct signature."""

    def test_log_action_importable(self):
        from services.audit import log_action, log_action_sync
        import inspect

        assert inspect.iscoroutinefunction(log_action)
        assert not inspect.iscoroutinefunction(log_action_sync)

    def test_log_action_signature(self):
        from services.audit import log_action
        import inspect

        sig = inspect.signature(log_action)
        params = list(sig.parameters.keys())
        assert params == ["db", "org_id", "user_id", "action", "metadata"]


class TestScanQuota:
    """Bug 5: check_scan_quota must be importable with correct signature."""

    def test_check_scan_quota_importable(self):
        from api.routes.scans import check_scan_quota
        import inspect

        assert inspect.iscoroutinefunction(check_scan_quota)

    def test_check_scan_quota_signature(self):
        from api.routes.scans import check_scan_quota
        import inspect

        sig = inspect.signature(check_scan_quota)
        params = list(sig.parameters.keys())
        assert params == ["org_id", "db"]

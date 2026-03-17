"""
CodeDebt Guardian — Centralized Configuration
Loads all settings from environment variables / .env file using Pydantic BaseSettings.
"""

from typing import List

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "CodeDebt Guardian"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v.startswith("change-me") or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and not the default value. "
                "Generate one with: openssl rand -hex 32"
            )
        return v

    # ── Database (PostgreSQL + pgvector) ────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://codedebt:codedebt@localhost:5432/codedebt"
    DATABASE_SYNC_URL: str = "postgresql://codedebt:codedebt@localhost:5432/codedebt"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Authentication ───────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # ── AI Providers (managed by AI Gateway — never exposed to clients) ─
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OLLAMA_URL: str = "http://localhost:11434"

    # ── GitHub Integration ───────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_APP_ID: str = ""
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # ── Stripe Billing ───────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO_MONTHLY: str = ""
    STRIPE_PRICE_ENTERPRISE_MONTHLY: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://codedebt-guardian.vercel.app",
    ]

    # ── Rate Limiting ────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_SCAN: str = "10/minute"
    RATE_LIMIT_FIX: str = "5/minute"

    # ── Business Logic ───────────────────────────────────────────────────
    DEV_HOURLY_RATE: float = 85.0
    CODEDEBT_MAX_PR_DOLLARS: float = 500.0
    MAX_FILES_PER_SCAN: int = 500
    MAX_SCAN_SIZE_MB: int = 100

    # ── Plan Limits ──────────────────────────────────────────────────────
    PLAN_LIMITS: dict = {
        "free": {"scans_monthly": 5, "auto_prs": False, "team_seats": 1},
        "pro": {"scans_monthly": 100, "auto_prs": True, "team_seats": 10},
        "enterprise": {"scans_monthly": 9999, "auto_prs": True, "team_seats": 9999},
    }

    # ── Observability ────────────────────────────────────────────────────
    OTEL_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "codedebt-guardian"

    # ── Legacy compat — keep old env var names working ──────────────────
    API_KEYS: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()

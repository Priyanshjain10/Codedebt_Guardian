"""
Shared test fixtures for CodeDebt Guardian test suite.
"""

import os
import pytest

# Set test environment variables before any imports
os.environ.setdefault("SECRET_KEY", "a]1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/codedebt_test")
os.environ.setdefault("DATABASE_SYNC_URL", "postgresql://test:test@localhost:5432/codedebt_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/14")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/13")
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GITHUB_TOKEN", "")
os.environ.setdefault("STRIPE_SECRET_KEY", "")

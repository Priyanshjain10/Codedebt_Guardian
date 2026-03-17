"""
CodeDebt Guardian — Database Engine & Session Factory
PostgreSQL + pgvector via SQLAlchemy 2.0 (async).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings


# ── Async engine (for FastAPI) ──────────────────────────────────────────
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (for Celery workers & Alembic) ─────────────────────────
sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

SyncSessionLocal = sessionmaker(bind=sync_engine)


# ── Base class ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency for FastAPI ──────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """Yield an async DB session for each request, auto-close on exit."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables (development convenience)."""
    async with async_engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose of the async engine."""
    await async_engine.dispose()

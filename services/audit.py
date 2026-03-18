"""
CodeDebt Guardian — Audit Logging Service
Writes to UsageLog for SOC 2 compliance and enterprise audit trails.
Never raises — audit failure must not block business operations.
"""
import uuid
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession
from models.db_models import UsageLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    action: str,
    metadata: Optional[dict] = None,
) -> None:
    """Write an audit log entry. Never raises — audit failure must not block ops."""
    try:
        entry = UsageLog(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            action=action,
            metadata_=metadata or {},
        )
        db.add(entry)
        async with db.begin_nested():
            await db.flush()
    except Exception as e:
        logger.warning(f"Audit log write failed (non-fatal): {e}")
        try:
            await db.rollback()
        except Exception:
            pass


def log_action_sync(
    db: SyncSession,
    org_id: UUID,
    user_id: UUID,
    action: str,
    metadata: Optional[dict] = None,
) -> None:
    """Sync version of log_action for Celery workers. Never raises."""
    try:
        entry = UsageLog(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            action=action,
            metadata_=metadata or {},
        )
        db.add(entry)
        db.flush()
    except Exception as e:
        logger.warning(f"Audit log write failed (non-fatal): {e}")
        try:
            db.rollback()
        except Exception:
            pass

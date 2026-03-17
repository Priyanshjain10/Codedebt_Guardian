"""
CodeDebt Guardian — API Key Routes
Create, list, and revoke per-org API keys.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import generate_api_key, get_current_user, APIKeyCreate
from database import get_db
from models.db_models import APIKeyModel, TeamMember, Team, User
from services.audit import log_action

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.post("", status_code=201)
async def create_api_key_endpoint(
    req: APIKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new API key (cdg_live_...).
    The full key is returned ONLY once — store it securely.
    """
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="No organization found")

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()

    full_key, prefix, key_hash = generate_api_key()

    api_key = APIKeyModel(
        org_id=team.org_id,
        user_id=user.id,
        key_prefix=prefix,
        key_hash=key_hash,
        label=req.label,
    )
    db.add(api_key)
    await db.flush()

    # Audit log: API key created
    await log_action(
        db,
        team.org_id,
        user.id,
        "api_key.created",
        {
            "key_prefix": prefix,
            "label": req.label,
        },
    )

    return {
        "id": str(api_key.id),
        "key": full_key,  # Only returned once!
        "prefix": prefix,
        "label": req.label,
        "message": "Store this key securely — it will not be shown again.",
    }


@router.get("")
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active API keys (prefix only, never full key)."""
    result = await db.execute(
        select(APIKeyModel)
        .where(APIKeyModel.user_id == user.id, APIKeyModel.is_active.is_(True))
        .order_by(APIKeyModel.created_at.desc())
    )
    keys = result.scalars().all()

    return {
        "api_keys": [
            {
                "id": str(k.id),
                "prefix": k.key_prefix,
                "label": k.label,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else "",
            }
            for k in keys
        ]
    }


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(
        select(APIKeyModel).where(
            APIKeyModel.id == uuid.UUID(key_id),
            APIKeyModel.user_id == user.id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.flush()

    # Audit log: API key revoked
    # Resolve org_id via the API key's user membership
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if membership:
        team = (
            await db.execute(select(Team).where(Team.id == membership.team_id))
        ).scalar_one()
        await log_action(
            db,
            team.org_id,
            user.id,
            "api_key.revoked",
            {
                "key_id": key_id,
                "key_prefix": api_key.key_prefix,
            },
        )

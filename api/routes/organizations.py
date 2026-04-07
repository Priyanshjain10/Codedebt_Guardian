"""
CodeDebt Guardian — Organization & Team Routes
Multi-tenant org management, team CRUD, member invitations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.auth import get_org_for_user
from database import get_db
from models.db_models import Organization, Team, TeamMember, User

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class CreateOrgRequest(BaseModel):
    name: str
    slug: str


class AddMemberRequest(BaseModel):
    email: str
    role: str = "member"


@router.get("")
async def list_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List organizations the user belongs to."""
    result = await db.execute(
        select(Organization)
        .join(Team, Team.org_id == Organization.id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id)
        .distinct()
    )
    orgs = result.scalars().all()

    return {
        "organizations": [
            {
                "id": str(o.id),
                "name": o.name,
                "slug": o.slug,
                "plan": o.plan,
                "created_at": o.created_at.isoformat() if o.created_at else "",
            }
            for o in orgs
        ]
    }


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get organization details."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Organization not found")
    org, _ = await get_org_for_user(org_uuid, user.id, db)

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "settings": org.settings or {},
        "created_at": org.created_at.isoformat() if org.created_at else "",
    }


@router.get("/{org_id}/teams")
async def list_teams(
    org_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List teams in an organization."""
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Organization not found")
    await get_org_for_user(org_uuid, user.id, db)
    result = await db.execute(
        select(Team)
        .options(selectinload(Team.members))
        .where(Team.org_id == org_uuid)
    )
    teams = result.scalars().all()

    return {
        "teams": [
            {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "member_count": len(t.members),
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in teams
        ]
    }


@router.get("/{org_id}/teams/{team_id}/members")
async def list_team_members(
    org_id: str,
    team_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List members of a team."""
    try:
        org_uuid = uuid.UUID(org_id)
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Team not found")
    await get_org_for_user(org_uuid, user.id, db)
    team = (
        await db.execute(select(Team).where(Team.id == team_uuid, Team.org_id == org_uuid))
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.user))
        .where(TeamMember.team_id == team_uuid)
    )
    members = result.scalars().all()

    return {
        "members": [
            {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else "",
                "user": {
                    "name": m.user.name,
                    "email": m.user.email,
                    "avatar_url": m.user.avatar_url,
                }
                if m.user
                else None,
            }
            for m in members
        ]
    }


@router.post("/{org_id}/teams/{team_id}/members")
async def add_team_member(
    org_id: str,
    team_id: str,
    req: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a team by email."""
    try:
        org_uuid = uuid.UUID(org_id)
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Team not found")
    await get_org_for_user(org_uuid, user.id, db, min_role="admin")
    team = (
        await db.execute(select(Team).where(Team.id == team_uuid, Team.org_id == org_uuid))
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Find user by email
    result = await db.execute(select(User).where(User.email == req.email))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already a member
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_uuid,
            TeamMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a team member")

    member = TeamMember(
        team_id=team_uuid,
        user_id=target_user.id,
        role=req.role,
    )
    db.add(member)
    await db.flush()

    return {"status": "added", "member_id": str(member.id)}

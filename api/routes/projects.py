"""
CodeDebt Guardian — Project Routes
CRUD for projects under teams.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.auth import get_project_for_user
from database import get_db
from models.db_models import Project, Team, TeamMember, User

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


class CreateProjectRequest(BaseModel):
    name: str
    repo_url: str
    default_branch: str = "main"
    team_id: Optional[str] = None


@router.post("", status_code=201)
async def create_project(
    req: CreateProjectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project linked to a GitHub repo."""
    # Get user's team
    if req.team_id:
        team_id = uuid.UUID(req.team_id)
    else:
        membership = (
            await db.execute(
                select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
            )
        ).scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=400, detail="No team found. Create an organization first."
            )
        team_id = membership.team_id

    project = Project(
        team_id=team_id,
        name=req.name,
        repo_url=req.repo_url,
        default_branch=req.default_branch,
    )
    db.add(project)
    await db.flush()

    return {
        "id": str(project.id),
        "name": project.name,
        "repo_url": project.repo_url,
        "default_branch": project.default_branch,
    }


@router.get("")
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    """List all projects the user has access to."""
    result = await db.execute(
        select(Project)
        .join(Team, Team.id == Project.team_id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id)
        .order_by(Project.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    projects = result.scalars().all()

    return {
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "repo_url": p.repo_url,
                "default_branch": p.default_branch,
                "created_at": p.created_at.isoformat() if p.created_at else "",
            }
            for p in projects
        ]
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project details."""
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    project, _ = await get_project_for_user(proj_uuid, user.id, db)

    # Get scan count
    from models.db_models import Scan

    scan_count = (
        await db.execute(
            select(func.count()).select_from(Scan).where(Scan.project_id == project.id)
        )
    ).scalar()

    return {
        "id": str(project.id),
        "name": project.name,
        "repo_url": project.repo_url,
        "default_branch": project.default_branch,
        "settings": project.settings or {},
        "scan_count": scan_count,
        "created_at": project.created_at.isoformat() if project.created_at else "",
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and all its scans."""
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    project, _ = await get_project_for_user(proj_uuid, user.id, db, min_role="admin")

    await db.delete(project)
    await db.flush()

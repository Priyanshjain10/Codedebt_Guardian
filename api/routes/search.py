"""
CodeDebt Guardian — Semantic Search API
Find similar code snippets using pgvector cosine_distance.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.auth import get_current_user
from database import get_db as get_async_db  # get_db yields AsyncSession
from models.db_models import User, Project, TeamMember
from services.embedding_pipeline import embedding_pipeline

router = APIRouter(prefix="/search", tags=["Semantic Search"])


@router.get("")
async def semantic_search(
    q: str = Query(..., description="Query text to search for"),
    project_id: str = Query(..., description="Project UUID to search within"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Perform semantic code search using pgvector."""
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id UUID")

    # Verify project access
    stmt = (
        select(Project)
        .join(TeamMember, TeamMember.team_id == Project.team_id)
        .where(Project.id == proj_uuid)
        .where(TeamMember.user_id == current_user.id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=404, detail="Project not found or access denied"
        )

    try:
        results = await embedding_pipeline.find_similar(
            project_id=str(proj_uuid), query=q, top_k=top_k
        )
        return {"query": q, "project_id": str(proj_uuid), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

"""
CodeDebt Guardian — Scan Routes
CRUD for scans: trigger, list, get results, create PRs, export CTO reports.
"""

import logging
import uuid
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user, get_current_user_optional
from database import get_db
from models.db_models import Scan, Project, User, TeamMember, Team, Subscription
from services.audit import log_action

from api.rate_limit import limiter

from slowapi.util import get_remote_address


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scans", tags=["Scans"])


# ── Rate Limits ──────────────────────────────────────────────────────────


def _get_auth_key(request: Request) -> str:
    """Key function for authenticated rate limits — keyed by Bearer token."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"auth:{auth[7:39]}"  # Use 32 chars for sufficient entropy
    return get_remote_address(request)


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_scan_uuid(scan_id: str) -> UUID:
    """Parse scan_id string to UUID, raising 404 (not 500) on bad format."""
    try:
        return uuid.UUID(scan_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Scan not found")


# ── Request / Response Models ─────────────────────────────────────────────


class CreateScanRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    project_id: Optional[str] = None
    auto_fix: bool = False
    max_prs: int = 3


class ScanResponse(BaseModel):
    id: str
    status: str
    repo_url: str
    branch: str
    summary: dict = {}
    duration_seconds: Optional[float] = None
    created_at: str

    model_config = {"from_attributes": True}


# ── Quota Enforcement ─────────────────────────────────────────────────────


async def check_scan_quota(org_id: UUID, db: AsyncSession) -> None:
    """Raise 402 if the org has hit their monthly scan limit."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.org_id == org_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if sub and sub.scans_used >= sub.scans_limit_monthly:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "scan_limit_exceeded",
                "message": f"Monthly scan limit of {sub.scans_limit_monthly} reached.",
                "upgrade_url": "/settings/billing",
                "resets_at": sub.current_period_end.isoformat()
                if sub.current_period_end
                else None,
            },
        )
    if sub:
        sub.scans_used += 1
        await db.flush()


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("", status_code=202)
@limiter.limit("5/minute")
async def create_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    req: CreateScanRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a new code analysis scan.
    Returns scan ID immediately; analysis runs in background via Celery.
    Connect to WebSocket /ws/scan/{scan_id} for real-time progress.
    """
    if not req.repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported")

    membership = None
    if user:
        membership = (
            await db.execute(
                select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
            )
        ).scalar_one_or_none()

    org_id: Optional[UUID] = None
    project_id: Optional[UUID] = None

    if req.project_id:
        # Explicit project_id always takes priority
        project_id = _parse_scan_uuid(req.project_id)

    elif membership:
        # Derive org / create implicit project when the user belongs to a team
        team = (
            await db.execute(select(Team).where(Team.id == membership.team_id))
        ).scalar_one()
        org_id = team.org_id

        # Enforce scan quota only when we have an org
        await check_scan_quota(org_id, db)

        project = Project(
            team_id=membership.team_id,
            name=req.repo_url.rstrip("/").split("/")[-1] or "unknown",
            repo_url=req.repo_url,
            default_branch=req.branch,
        )
        db.add(project)
        await db.flush()
        project_id = project.id

    elif user:
        raise HTTPException(
            status_code=400,
            detail="You must belong to a team, or explicitly supply a project_id.",
        )
    else:
        # Unauthenticated direct scan
        # For unauthenticated scans, we don't create a project or associate with an org.
        # The scan will be created without a project_id, which is allowed by the schema.
        # triggered_by will be NULL.
        pass

    # Create the scan record — project_id is now guaranteed non-null if authenticated and project context exists
    scan = Scan(
        project_id=project_id,
        triggered_by=user.id if user else None,
        branch=req.branch,
        status="queued",
    )
    db.add(scan)
    await db.flush()
    scan_id = str(scan.id)

    # Audit log
    if org_id:
        await log_action(
            db,
            org_id,
            user.id,
            "scan.created",
            {
                "scan_id": scan_id,
                "repo_url": req.repo_url,
                "branch": req.branch,
            },
        )

    # Commit BEFORE adding background task to prevent race condition
    # (background task uses SyncSession and reads DB immediately)
    await db.commit()

    # Enqueue scan as FastAPI background task (no Celery needed)
    from workers.tasks import run_scan_task

    background_tasks.add_task(run_scan_task, scan_id, req.repo_url, req.branch)

    return {
        "scan_id": scan_id,
        "status": "queued",
        "ws_url": f"/ws/scan/{scan_id}",
        "message": "Scan queued. Connect to WebSocket for live progress.",
    }


@router.get("")
async def list_scans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    """List scans triggered by the authenticated user."""
    query = select(Scan).where(Scan.triggered_by == user.id)
    if status:
        query = query.where(Scan.status == status)
    query = query.order_by(Scan.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    scans = result.scalars().all()

    count_q = select(func.count()).select_from(Scan).where(Scan.triggered_by == user.id)
    total = (await db.execute(count_q)).scalar()

    return {
        "scans": [
            {
                "id": str(s.id),
                "status": s.status,
                "branch": s.branch,
                "scan_type": getattr(s, "scan_type", "repo") or "repo",
                "pr_number": getattr(s, "pr_number", None),
                "debt_score": getattr(s, "debt_score", None),
                "summary": s.summary or {},
                "duration_seconds": s.duration_seconds,
                "created_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in scans
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/latest")
async def get_latest_scan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent completed scan for the authenticated user.
    Used by the sidebar nav shortcut links.
    """
    result = await db.execute(
        select(Scan)
        .where(Scan.triggered_by == user.id, Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .limit(1)
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="No completed scans found")

    return {
        "id": str(scan.id),
        "status": scan.status,
        "branch": scan.branch,
        "scan_type": getattr(scan, "scan_type", "repo") or "repo",
        "pr_number": getattr(scan, "pr_number", None),
        "debt_score": getattr(scan, "debt_score", None),
        "summary": scan.summary or {},
        "detection": scan.detection_results or {},
        "ranked_issues": scan.ranked_issues or [],
        "fix_proposals": scan.fix_proposals or [],
        "hotspots": scan.hotspots or [],
        "tdr": scan.tdr or {},
        "duration_seconds": scan.duration_seconds,
        "created_at": scan.created_at.isoformat() if scan.created_at else "",
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }


@router.get("/pull-requests")
async def list_pull_requests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    """List Pull Requests created from the user's scans.
    Placeholder array returned for now since PullRequest model implementation is not complete.
    Join logic simulated based on spec.
    """
    return {
        "pull_requests": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{scan_id}")
async def get_scan(
    scan_id: str,
    user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get full scan results by ID."""
    result = await db.execute(select(Scan).where(Scan.id == _parse_scan_uuid(scan_id)))
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "id": str(scan.id),
        "status": scan.status,
        "branch": scan.branch,
        "scan_type": getattr(scan, "scan_type", "repo") or "repo",
        "pr_number": getattr(scan, "pr_number", None),
        "debt_score": getattr(scan, "debt_score", None),
        "summary": scan.summary or {},
        "detection": scan.detection_results or {},
        "ranked_issues": scan.ranked_issues or [],
        "fix_proposals": scan.fix_proposals or [],
        "hotspots": scan.hotspots or [],
        "tdr": scan.tdr or {},
        "duration_seconds": scan.duration_seconds,
        "created_at": scan.created_at.isoformat() if scan.created_at else "",
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }


@router.get("/{scan_id}/report")
async def get_scan_report(
    scan_id: str,
    format: str = Query("html", pattern="^(html|pdf)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate CTO executive report for a completed scan.

    Returns HTML by default. Pass ?format=pdf to get a PDF download
    (requires weasyprint). Falls back to HTML with X-Report-Format header
    if weasyprint is not installed.
    """
    result = await db.execute(
        select(Scan)
        .options(selectinload(Scan.project))
        .where(Scan.id == _parse_scan_uuid(scan_id))
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Scan not yet completed (current status: {scan.status})",
        )

    # Build analysis dict that CTOReportGenerator expects
    analysis_data = {
        "detection": scan.detection_results or {},
        "ranked_issues": scan.ranked_issues or [],
        "fix_proposals": scan.fix_proposals or [],
        "hotspots": scan.hotspots or [],
        "tdr": scan.tdr or {},
        "knowledge_silos": [],
    }

    try:
        from tools.cto_report import CTOReportGenerator

        html_content = CTOReportGenerator().generate(
            analysis_data,
            repo_url=scan.project.repo_url if scan.project else "",
        )
    except Exception as e:
        logger.error(
            f"CTOReportGenerator failed for scan {scan_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    if format == "html":
        return HTMLResponse(content=html_content)

    # PDF rendering — try weasyprint, fall back gracefully to HTML
    try:
        from weasyprint import HTML as WeasyHTML

        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="debt-report-{scan_id[:8]}.pdf"'
            },
        )
    except ImportError:
        logger.warning("weasyprint not installed — returning HTML with fallback header")
        return HTMLResponse(
            content=html_content,
            headers={"X-Report-Format": "html-fallback"},
        )
    except Exception as pdf_err:
        logger.warning(f"PDF rendering failed: {pdf_err} — returning HTML fallback")
        return HTMLResponse(
            content=html_content,
            headers={
                "X-Report-Format": "html-fallback",
                "X-PDF-Error": str(pdf_err)[:200],
            },
        )


@router.post("/{scan_id}/fix/{fix_index}")
async def create_fix_pr(
    scan_id: str,
    fix_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a GitHub PR for a specific fix from a completed scan.

    Requires Pro plan or higher for auto-PR capability.
    """
    scan_uuid = _parse_scan_uuid(scan_id)
    result = await db.execute(select(Scan).where(Scan.id == scan_uuid))
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != "completed":
        raise HTTPException(status_code=400, detail="Scan not completed yet")

    # ── Phase 4.3: Enforce auto-PR plan gate ────────────────────────────
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()

    if membership:
        team = (
            await db.execute(select(Team).where(Team.id == membership.team_id))
        ).scalar_one()
        sub = (
            await db.execute(
                select(Subscription)
                .where(
                    Subscription.org_id == team.org_id,
                    Subscription.status == "active",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        plan = sub.plan if sub else "free"

        from config import settings

        if not settings.PLAN_LIMITS.get(plan, {}).get("auto_prs", False):
            raise HTTPException(
                status_code=402,
                detail="Auto-fix PRs require Pro plan. Upgrade at /settings/billing.",
            )

    fixes = scan.fix_proposals or []
    ranked = scan.ranked_issues or []

    if fix_index >= len(fixes):
        raise HTTPException(
            status_code=400,
            detail=f"Fix index {fix_index} out of range (scan has {len(fixes)} fixes)",
        )

    fix = fixes[fix_index]
    issue = ranked[fix_index] if fix_index < len(ranked) else {}

    # Get repo URL from project
    project = (
        await db.execute(select(Project).where(Project.id == scan.project_id))
    ).scalar_one_or_none()
    repo_url = project.repo_url if project else ""

    if not repo_url:
        raise HTTPException(status_code=400, detail="No repo URL found for this scan")

    try:
        from tools.pr_generator import PRGenerator

        pr = PRGenerator().create_fix_pr(
            repo_url=repo_url, fix_proposal=fix, issue=issue
        )
        if not pr:
            return {
                "status": "skipped",
                "message": "This issue type cannot be auto-fixed",
            }
        return {
            "status": "created",
            "pr_url": pr.get("html_url") or pr.get("url"),
            "pr_number": pr.get("number"),
            "title": pr.get("title", ""),
        }
    except Exception as e:
        logger.error(
            f"PR creation failed for scan {scan_id} fix {fix_index}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"PR creation failed: {str(e)}")

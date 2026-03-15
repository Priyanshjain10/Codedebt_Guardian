"""
CodeDebt Guardian — Analytics Routes
Aggregates debt scores, scans run, fixes generated, and PRs created.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from database import get_db
from models.db_models import Scan, PullRequest, User

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/stats")
async def get_analytics_stats(
    days: int = Query(30, description="Number of days to look back"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated analytics stats for the authenticated user."""

    if days <= 0:
        cutoff_date = datetime.min.replace(tzinfo=timezone.utc)
    else:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(Scan)
        .where(
            and_(
                Scan.triggered_by == user.id,
                Scan.created_at >= cutoff_date,
            )
        )
        .order_by(Scan.created_at.asc())
    )

    result = await db.execute(query)
    scans = result.scalars().all()
    completed_scans = [s for s in scans if s.status == "completed"]

    scans_run = len(scans)
    total_issues = sum(
        s.summary.get("total_issues", 0) for s in completed_scans if s.summary
    )
    fixes_generated = sum(
        s.summary.get("fixes_proposed", 0) for s in completed_scans if s.summary
    )

    # TODO: Once PR creation populates PullRequest properly, this will be accurate.
    # We can also join against PullRequest.
    pr_query = (
        select(func.count(PullRequest.id))
        .join(Scan)
        .where(
            and_(Scan.triggered_by == user.id, PullRequest.created_at >= cutoff_date)
        )
    )
    prs_created = (await db.execute(pr_query)).scalar() or 0

    debt_trend = []
    category_breakdown = {
        "security": 0,
        "performance": 0,
        "maintainability": 0,
        "complexity": 0,
        "documentation": 0,
        "testing": 0,
        "dependencies": 0,
    }
    severity_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    # Aggregate by date for trend
    daily_debt = {}

    for s in completed_scans:
        if not s.summary:
            continue

        date_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else ""
        debt_score = s.summary.get("debt_score")

        if debt_score is not None and date_str:
            daily_debt[date_str] = {
                "date": date_str,
                "debt_score": debt_score,
                "scan_id": str(s.id),
            }

        # Categories
        for issue in s.ranked_issues or []:
            cat = issue.get("category", "").lower()
            if cat in category_breakdown:
                category_breakdown[cat] += 1

        # Severities
        severity_breakdown["CRITICAL"] += s.summary.get("critical", 0)
        severity_breakdown["HIGH"] += s.summary.get("high", 0)
        severity_breakdown["MEDIUM"] += s.summary.get("medium", 0)
        severity_breakdown["LOW"] += s.summary.get("low", 0)

    debt_trend = list(daily_debt.values())

    # Sort by date
    debt_trend.sort(key=lambda x: x["date"])

    return {
        "scans_run": scans_run,
        "total_issues": total_issues,
        "fixes_generated": fixes_generated,
        "prs_created": prs_created,
        "debt_trend": debt_trend,
        "category_breakdown": category_breakdown,
        "severity_breakdown": severity_breakdown,
    }

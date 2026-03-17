"""
CodeDebt Guardian — GitHub App Installation Routes
Install redirect, callback, repo sync, and repo listing.
"""

import logging
import time
from datetime import datetime, timezone

import jwt as pyjwt
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from config import settings
from database import get_db
from models.db_models import (
    GitHubInstallation,
    Project,
    Team,
    TeamMember,
    User,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/github", tags=["GitHub"])

GITHUB_API = "https://api.github.com"


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_app_slug() -> str:
    """Derive GitHub App slug from APP_ID. Override via GITHUB_APP_SLUG env."""
    import os

    return os.getenv("GITHUB_APP_SLUG", "codedebt-guardian")


def _make_app_jwt() -> str:
    """Create a short-lived JWT signed with the GitHub App private key."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": settings.GITHUB_APP_ID,
    }
    return pyjwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")


def _get_installation_token(installation_id: int) -> tuple[str, datetime]:
    """Exchange App JWT for an installation access token. Returns (token, expires_at)."""
    app_jwt = _make_app_jwt()
    resp = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    return data["token"], expires_at


def _fetch_installation_repos(token: str) -> list[dict]:
    """Fetch all repositories accessible by an installation token."""
    repos = []
    url = f"{GITHUB_API}/installation/repositories?per_page=100"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    while url:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        repos.extend(data.get("repositories", []))
        # Handle pagination
        link = resp.headers.get("Link", "")
        url = None
        if 'rel="next"' in link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
    return repos


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/install")
async def github_install_redirect(
    user: User = Depends(get_current_user),
):
    """Redirect user to GitHub App installation page."""
    slug = _get_app_slug()
    install_url = f"https://github.com/apps/{slug}/installations/new"
    return RedirectResponse(url=install_url, status_code=302)


@router.get("/callback")
async def github_install_callback(
    installation_id: int = Query(...),
    setup_action: str = Query("install"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GitHub redirects here after the user installs the App.
    Stores the installation and syncs accessible repositories as Project records.
    """
    if setup_action not in ("install", "update"):
        return {
            "status": "ignored",
            "reason": f"Unhandled setup_action: {setup_action}",
        }

    # Get user's org
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=400, detail="You must belong to a team first.")

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()
    org_id = team.org_id

    # Check if installation already stored
    existing = (
        await db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == installation_id
            )
        )
    ).scalar_one_or_none()

    if existing:
        # Update org association if needed
        if existing.org_id != org_id:
            existing.org_id = org_id
        await db.flush()
        install_record = existing
    else:
        # Fetch installation info from GitHub
        try:
            app_jwt = _make_app_jwt()
            info_resp = requests.get(
                f"{GITHUB_API}/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            info_resp.raise_for_status()
            info = info_resp.json()
            account_login = info.get("account", {}).get("login", "unknown")
            account_type = info.get("account", {}).get("type", "User")
        except Exception as e:
            logger.warning(f"Could not fetch installation info: {e}")
            account_login = "unknown"
            account_type = "User"

        install_record = GitHubInstallation(
            org_id=org_id,
            installation_id=installation_id,
            account_login=account_login,
            account_type=account_type,
        )
        db.add(install_record)
        await db.flush()

    # Sync repos
    synced = await _sync_repos_for_installation(install_record, membership.team_id, db)

    return {
        "status": "connected",
        "installation_id": installation_id,
        "account": install_record.account_login,
        "repos_synced": synced,
    }


@router.get("/repos")
async def list_github_repos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all GitHub repositories connected via installed GitHub Apps."""
    # Get user's org installations
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()

    if not membership:
        return {"repos": []}

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()

    installations = (
        (
            await db.execute(
                select(GitHubInstallation).where(
                    GitHubInstallation.org_id == team.org_id
                )
            )
        )
        .scalars()
        .all()
    )

    all_repos = []
    for inst in installations:
        try:
            token, expires = _get_installation_token(inst.installation_id)
            repos = _fetch_installation_repos(token)
            for r in repos:
                # Check if already a Project
                existing_project = (
                    await db.execute(
                        select(Project).where(Project.repo_url == r["html_url"])
                    )
                ).scalar_one_or_none()

                all_repos.append(
                    {
                        "name": r["full_name"],
                        "url": r["html_url"],
                        "private": r.get("private", False),
                        "default_branch": r.get("default_branch", "main"),
                        "connected": existing_project is not None,
                        "project_id": str(existing_project.id)
                        if existing_project
                        else None,
                    }
                )
        except Exception as e:
            logger.warning(
                f"Failed to list repos for installation {inst.installation_id}: {e}"
            )

    return {"repos": all_repos, "installation_count": len(installations)}


@router.post("/repos/sync")
async def sync_github_repos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-sync all repositories from GitHub App installations and create Project records."""
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=400, detail="No team membership found.")

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()

    installations = (
        (
            await db.execute(
                select(GitHubInstallation).where(
                    GitHubInstallation.org_id == team.org_id
                )
            )
        )
        .scalars()
        .all()
    )

    total_synced = 0
    for inst in installations:
        synced = await _sync_repos_for_installation(inst, membership.team_id, db)
        total_synced += synced

    return {"status": "synced", "repos_synced": total_synced}


# ── Internal Sync Logic ──────────────────────────────────────────────────


async def _sync_repos_for_installation(
    installation: GitHubInstallation,
    team_id,
    db: AsyncSession,
) -> int:
    """Fetch repos from GitHub and create Project records for new ones."""
    try:
        token, expires = _get_installation_token(installation.installation_id)
        installation.access_token = token
        installation.token_expires_at = expires
    except Exception as e:
        logger.error(f"Failed to get installation token: {e}")
        return 0

    try:
        repos = _fetch_installation_repos(token)
    except Exception as e:
        logger.error(f"Failed to fetch repos: {e}")
        return 0

    count = 0
    for r in repos:
        repo_url = r["html_url"]
        existing = (
            await db.execute(select(Project).where(Project.repo_url == repo_url))
        ).scalar_one_or_none()

        if not existing:
            project = Project(
                team_id=team_id,
                name=r.get("name", repo_url.split("/")[-1]),
                repo_url=repo_url,
                default_branch=r.get("default_branch", "main"),
            )
            db.add(project)
            count += 1

    installation.repos_synced_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info(
        f"Synced {count} new repos for installation {installation.installation_id}"
    )
    return count

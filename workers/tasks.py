"""
CodeDebt Guardian — Celery Tasks
Background jobs for scan analysis, code embedding, and PR generation.
Each task publishes progress to Redis pub/sub for WebSocket consumption.
"""

import json
import logging
import time
import uuid
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Any, Dict
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import redis

from config import settings
from workers.celery_app import celery_app
from database import SyncSessionLocal
from models.db_models import Scan, Project
from services.audit import log_action_sync

logger = logging.getLogger(__name__)

try:
    _redis = redis.from_url(settings.REDIS_URL)
except Exception as _redis_err:
    import logging as _log

    _log.getLogger(__name__).warning(f"Redis unavailable: {_redis_err}")
    _redis = None


def _publish_progress(scan_id: str, message: str, phase: str = "", percent: int = 0):
    """Publish scan progress event to Redis pub/sub for WebSocket relay."""
    event = json.dumps(
        {
            "type": "scan.progress",
            "scan_id": scan_id,
            "phase": phase,
            "message": message,
            "percent": percent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    if _redis:
        _redis.publish(f"scan:{scan_id}", event)


def _publish_complete(scan_id: str, data: Dict[str, Any]):
    """Publish scan completion event."""
    event = json.dumps(
        {
            "type": "scan.complete",
            "scan_id": scan_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        default=str,
    )
    if _redis:
        _redis.publish(f"scan:{scan_id}", event)


def _publish_error(scan_id: str, message: str):
    """Publish scan error event."""
    event = json.dumps(
        {
            "type": "scan.error",
            "scan_id": scan_id,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    if _redis:
        _redis.publish(f"scan:{scan_id}", event)


@celery_app.task(bind=True, name="workers.tasks.run_scan_analysis", max_retries=2)
def run_scan_analysis(self, scan_id: str, repo_url: str, branch: str = "main"):
    """
    Full scan pipeline: detect → rank → fix → embed.
    Runs in a background worker; publishes progress via Redis pub/sub.
    """
    db = SyncSessionLocal()
    start_time = time.time()

    # BUG FIX: scan_id arrives as a str but Scan.id is a UUID column.
    # asyncpg/psycopg2 require an explicit uuid.UUID object.
    try:
        scan_uuid = uuid.UUID(scan_id)
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid scan_id format: {scan_id!r} — {e}")
        return

    try:
        # Mark scan as running
        scan = db.execute(select(Scan).where(Scan.id == scan_uuid)).scalar_one_or_none()

        if not scan:
            logger.error(f"Scan {scan_id} not found in database")
            return

        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()

        _publish_progress(scan_id, "Initializing analysis pipeline...", "init", 5)

        # Phase 1: Debt Detection
        from agents.orchestrator import CodeDebtOrchestrator

        orchestrator = CodeDebtOrchestrator(use_persistent_memory=False)

        # ~ Incremental Scanning Logic (Task 6) ~
        from tools.github_tool import GitHubTool

        github = GitHubTool()

        _publish_progress(
            scan_id, "[1/4] 🕵️ Fetching repository data...", "detection", 8
        )
        repo_data = github.fetch_repo_contents(repo_url, branch)
        temp_dir = repo_data.pop("_temp_dir", None)

        # Get head sha for incremental tracking
        owner, repo = github.parse_repo_url(repo_url)
        head_sha = "unknown"
        has_changes = True
        try:
            commits_url = (
                f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
            )
            commits_res = github._get(commits_url)
            head_sha = commits_res.json().get("sha", "unknown")
            scan.commit_sha = head_sha
            db.commit()

            # Find previous successful scan for this repo
            prev_scan = db.execute(
                select(Scan)
                .where(Scan.repo_url == repo_url)
                .where(Scan.status == "completed")
                .where(Scan.id != scan_uuid)
                .where(Scan.commit_sha.is_not(None))
                .order_by(Scan.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if prev_scan and prev_scan.commit_sha and prev_scan.commit_sha != head_sha:
                compare_url = f"https://api.github.com/repos/{owner}/{repo}/compare/{prev_scan.commit_sha}...{head_sha}"
                compare_res = github._get(compare_url)
                compare_data = compare_res.json()
                changed_files = {f["filename"] for f in compare_data.get("files", [])}

                if not changed_files:
                    has_changes = False
                    _publish_progress(
                        scan_id,
                        "[1/4] ⚡ Incremental Scan: No relevant files changed since last scan.",
                        "detection",
                        15,
                    )
                else:
                    _publish_progress(
                        scan_id,
                        f"[1/4] ⚡ Incremental Scan: Found {len(changed_files)} changed files.",
                        "detection",
                        15,
                    )
                    repo_data["files"] = (
                        f for f in repo_data["files"] if f["name"] in changed_files
                    )
        except Exception as e:
            logger.warning(f"Incremental scan check failed, processing all files: {e}")

        all_issues = []
        files_scanned = 0

        if has_changes:
            _publish_progress(
                scan_id,
                "[1/4] 🕵️ Running debt detection (Thread Pool)...",
                "detection",
                20,
            )

            # Build list from generator for parallel processing (careful with memory, but local_paths are small dicts)
            file_dicts = list(repo_data["files"])
            total_files = len(file_dicts)

            # Using ThreadPool inside Celery worker for IO-bound AST/LLM ops
            max_workers = min(32, (os.cpu_count() or 1) * 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Helper to process a single file via the agent
                def scan_file(file_info):
                    try:
                        # Extract static and AI logic from DebtDetectionAgent
                        agent = orchestrator.detection_agent
                        file_issues = []
                        # 1. Static
                        if file_info["name"].endswith(".py"):
                            file_issues.extend(agent._run_static_analysis(file_info))
                        # 2. AI (skip static for AI simplicity in batch)
                        elif file_info["name"].endswith((".js", ".ts", ".jsx", ".tsx")):
                            from agents.debt_detection_agent import (
                                JS_SUPPORT,
                                _js_analyzer,
                            )

                            if JS_SUPPORT:
                                file_issues.extend(_js_analyzer.analyze(file_info))
                        return file_issues
                    except Exception as e:
                        logger.error(f"Failed to scan {file_info.get('name')}: {e}")
                        return []

                futures = {executor.submit(scan_file, f): f for f in file_dicts}

                for i, future in enumerate(as_completed(futures), 1):
                    file_issues = future.result()
                    all_issues.extend(file_issues)
                    files_scanned += 1

                    if i % max(1, total_files // 10) == 0:
                        _publish_progress(
                            scan_id,
                            f"[1/4] 🕵️ Scanned {i}/{total_files} files...",
                            "detection",
                            20 + int((i / total_files) * 10),
                        )

            # Deduplicate and build final detection results
            all_issues = orchestrator.detection_agent._deduplicate(all_issues)
            detection_results = {
                "repo_url": repo_url,
                "branch": branch,
                "repo_metadata": repo_data.get("repo_metadata", {}),
                "files_scanned": files_scanned,
                "total_issues": len(all_issues),
                "issues": all_issues,
                "stats": orchestrator.detection_agent._compute_stats(all_issues),
            }
        else:
            # No changes, zero issues detected
            detection_results = {
                "repo_url": repo_url,
                "branch": branch,
                "repo_metadata": repo_data.get("repo_metadata", {}),
                "files_scanned": 0,
                "total_issues": 0,
                "issues": [],
                "stats": {},
            }

        try:
            total_issues = detection_results.get("total_issues", 0)
            _publish_progress(
                scan_id,
                f"[1/4] ✅ Scanned {files_scanned} files — found {total_issues} issues",
                "detection",
                30,
            )

            # Phase 2: Priority Ranking
            _publish_progress(
                scan_id, "[2/4] 📊 Ranking issues by business impact...", "ranking", 35
            )
            ranked_results = orchestrator.rank_debt(detection_results)
            critical = sum(1 for i in ranked_results if i.get("priority") == "CRITICAL")
            high = sum(1 for i in ranked_results if i.get("priority") == "HIGH")
            _publish_progress(
                scan_id,
                f"[2/4] ✅ Ranked {len(ranked_results)} issues — {critical} CRITICAL, {high} HIGH",
                "ranking",
                55,
            )

            # Phase 3: Fix Proposals
            _publish_progress(
                scan_id, "[3/4] 🔧 Generating AI fix proposals...", "fixes", 60
            )
            fix_proposals = orchestrator.propose_fixes(
                ranked_results[:10],
                project_id=str(scan.project_id) if scan.project_id else None,
            )
            _publish_progress(
                scan_id,
                f"[3/4] ✅ Generated {len(fix_proposals)} fix proposals",
                "fixes",
                80,
            )

            # Phase 4: TDR + Hotspots
            _publish_progress(
                scan_id, "[4/4] 🔥 Computing health score & hotspots...", "metrics", 85
            )
            hotspots = []
            tdr = {}
            try:
                from tools.hotspot_analyzer import HotspotAnalyzer

                hotspots = HotspotAnalyzer().analyze(
                    detection_results.get("issues", [])
                )
            except Exception as hot_err:
                logger.warning(f"HotspotAnalyzer failed (non-fatal): {hot_err}")
            try:
                from tools.tdr_calculator import TDRCalculator

                tdr = TDRCalculator().calculate(
                    issues=detection_results.get("issues", []),
                    files_scanned=detection_results.get("files_scanned", 0),
                )
            except Exception as tdr_err:
                logger.warning(f"TDRCalculator failed (non-fatal): {tdr_err}")

            duration = time.time() - start_time

            # Build summary
            metrics = orchestrator.get_metrics()
            tu = metrics.get("token_usage", {})
            summary = {
                "total_issues": total_issues,
                "files_scanned": files_scanned,
                "critical": critical,
                "high": high,
                "medium": sum(
                    1 for i in ranked_results if i.get("priority") == "MEDIUM"
                ),
                "low": sum(1 for i in ranked_results if i.get("priority") == "LOW"),
                "fixes_proposed": len(fix_proposals),
                "grade": tdr.get("grade", "N/A"),
                "tokens_input": tu.get("input", 0),
                "tokens_output": tu.get("output", 0),
                "model_usage": tu.get("model_usage", {"groq": 0, "gemini": 0}),
            }

            # Update DB
            scan.status = "completed"
            scan.summary = summary
            scan.detection_results = detection_results
            scan.ranked_issues = ranked_results
            scan.fix_proposals = fix_proposals
            scan.hotspots = hotspots
            scan.tdr = tdr
            scan.duration_seconds = round(duration, 2)
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()

            _publish_progress(
                scan_id,
                f"[4/4] ✅ Analysis completed in {duration:.1f}s",
                "complete",
                100,
            )
            _publish_complete(
                scan_id,
                {
                    "summary": summary,
                    "tdr": tdr,
                    "ranked_issues": ranked_results,
                    "fix_proposals": fix_proposals,
                    "hotspots": hotspots,
                    "detection": detection_results,
                    "duration_seconds": round(duration, 2),
                },
            )

            logger.info(
                f"Scan {scan_id} completed: {total_issues} issues in {duration:.1f}s"
            )

            # Audit log: scan completed (sync version for Celery)
            if scan.project_id:
                project = db.execute(
                    select(Project).where(Project.id == scan.project_id)
                ).scalar_one_or_none()
                if project:
                    from models.db_models import Team

                    team = db.execute(
                        select(Team).where(Team.id == project.team_id)
                    ).scalar_one_or_none()
                    if team and scan.triggered_by:
                        log_action_sync(
                            db,
                            team.org_id,
                            scan.triggered_by,
                            "scan.completed",
                            {
                                "scan_id": scan_id,
                                "total_issues": total_issues,
                                "grade": tdr.get("grade", "N/A"),
                            },
                        )
                        db.commit()

            # Trigger async embedding generation
            if scan.project_id:
                generate_embeddings.delay(
                    scan_id=scan_id,
                    project_id=str(scan.project_id),
                    repo_url=repo_url,
                    branch=branch,
                )
                logger.info(f"Queued async embeddings for project {scan.project_id}")

        finally:
            # Always clean up temp directory regardless of success or failure
            if temp_dir:
                try:
                    temp_dir.cleanup()
                except Exception as cleanup_err:
                    logger.warning(f"Temp dir cleanup failed: {cleanup_err}")

    except Exception as e:
        logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)
        _publish_error(scan_id, str(e))

        # BUG FIX: Re-query scan in except block — it may not be bound if the
        # exception was thrown before the initial query (e.g. DB connection failure).
        try:
            failed_scan = db.execute(
                select(Scan).where(Scan.id == scan_uuid)
            ).scalar_one_or_none()
            if failed_scan:
                failed_scan.status = "failed"
                failed_scan.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as mark_err:
            logger.error(f"Failed to mark scan as failed: {mark_err}")

        raise self.retry(exc=e, countdown=30)

    finally:
        db.close()


@celery_app.task(name="workers.tasks.generate_embeddings")
def generate_embeddings(
    scan_id: str, project_id: str, repo_url: str, branch: str = "main"
):
    """Generate code embeddings for vector search (runs after scan asynchronously)."""
    import os
    import tempfile
    import asyncio
    from git import Repo
    from services.embedding_pipeline import embedding_pipeline

    logger.info(f"Generating embeddings for scan {scan_id} / project {project_id}")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Cloning {repo_url} (branch: {branch}) for embeddings...")
            Repo.clone_from(repo_url, temp_dir, depth=1, branch=branch)

            files_to_embed = []
            valid_exts = (
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".go",
                ".java",
                ".cpp",
                ".c",
                ".h",
                ".md",
            )

            for root, dirs, files in os.walk(temp_dir):
                if ".git" in dirs:
                    dirs.remove(".git")
                for file_name in files:
                    if not file_name.endswith(valid_exts):
                        continue
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, temp_dir)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            files_to_embed.append(
                                {"name": rel_path, "content": f.read()}
                            )
                    except Exception:
                        pass

            if files_to_embed:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    embedding_pipeline.embed_scan_results(project_id, files_to_embed)
                )
                logger.info(
                    f"Finished embedding {len(files_to_embed)} files for project {project_id}"
                )
            else:
                logger.warning(f"No embeddable files found in {repo_url}")

    except Exception as e:
        logger.error(
            f"Failed to generate embeddings for project {project_id}: {e}",
            exc_info=True,
        )


@celery_app.task(name="workers.tasks.create_fix_pr")
def create_fix_pr(repo_url: str, fix_proposal: dict, issue: dict, scan_id: str = ""):
    """Create a GitHub PR for a specific fix proposal."""
    try:
        from tools.pr_generator import PRGenerator

        pr = PRGenerator().create_fix_pr(
            repo_url=repo_url,
            fix_proposal=fix_proposal,
            issue=issue,
        )
        if pr and scan_id:
            _publish_progress(
                scan_id, f"✅ PR created: {pr.get('title', '')}", "pr", 100
            )
        return pr
    except Exception as e:
        logger.error(f"PR creation failed: {e}", exc_info=True)
        if scan_id:
            _publish_error(scan_id, f"PR creation failed: {e}")
        return None


@celery_app.task(name="workers.tasks.run_scheduled_scans")
def run_scheduled_scans():
    """Beat task: run scheduled autopilot scans for configured projects."""
    logger.info("Running scheduled scan check...")
    # In production: query projects with autopilot enabled, enqueue scan for each
    pass


async def run_scan_task(scan_id: str, repo_url: str, branch: str = "main"):
    """Async wrapper for scan pipeline - runs as FastAPI BackgroundTask."""
    import asyncio
    import concurrent.futures

    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    await loop.run_in_executor(executor, _run_scan_sync, scan_id, repo_url, branch)


def _run_scan_sync(scan_id: str, repo_url: str, branch: str = "main"):
    """Synchronous scan pipeline called from run_scan_task via thread executor."""
    # Use Celery .apply() for synchronous eager execution in same process
    run_scan_analysis.apply(args=[scan_id, repo_url, branch])

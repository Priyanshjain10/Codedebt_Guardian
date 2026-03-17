import logging
import requests
import re
import ast
import uuid
from datetime import datetime, timezone
from typing import List

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# ── Safe auto-fix issue types ──────────────────────────────────────────
SAFE_AUTO_FIX_TYPES = {
    "bare_except",
    "hardcoded_password",
    "hardcoded_api_key",
    "unpinned_dependencies",
}

MARKER = "<!-- codedebt-guardian -->"


def extract_added_lines(patch: str) -> str:
    """Extract only lines starting with '+' (excluding '+++')."""
    added = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return "\n".join(added)


def _analyze_content(file_info: dict) -> List[dict]:
    """Run static analysis on file content using DebtDetectionAgent's AST checks."""
    try:
        from agents.debt_detection_agent import DebtDetectionAgent

        agent = DebtDetectionAgent.__new__(DebtDetectionAgent)
        return agent._run_static_analysis(file_info)
    except Exception as e:
        logger.warning(f"Failed to use DebtDetectionAgent, falling back: {e}")
        return _minimal_static_analysis(file_info)


def _minimal_static_analysis(file_info: dict) -> List[dict]:
    """Minimal fallback inline analysis for webhooks if agent fails."""
    content = file_info.get("content", "")
    filename = file_info.get("name", "unknown")
    issues = []

    if not content.strip():
        return issues

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == "except:" or stripped.startswith("except: "):
            issues.append(
                {
                    "type": "bare_except",
                    "severity": "MEDIUM",
                    "description": "Bare 'except:' catches all exceptions",
                    "location": f"{filename}:{i}",
                    "confidence": 0.95,
                }
            )

    cred_patterns = [
        (
            r'(password|passwd|pwd)\s*=\s*(?:"[^"]+"|\x27[^\x27]+\x27)',
            "hardcoded_password",
        ),
        (
            r'(api_key|apikey|secret_key)\s*=\s*(?:"[^"]+"|\x27[^\x27]+\x27)',
            "hardcoded_api_key",
        ),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, debt_type in cred_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(
                    {
                        "type": debt_type,
                        "severity": "CRITICAL",
                        "description": "Possible hardcoded credential detected",
                        "location": f"{filename}:{i}",
                        "confidence": 0.92,
                    }
                )

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = (node.end_lineno or 0) - node.lineno
                if func_lines > 50:
                    issues.append(
                        {
                            "type": "long_method",
                            "severity": "MEDIUM" if func_lines < 100 else "HIGH",
                            "description": f"Function '{node.name}' is {func_lines} lines long",
                            "location": f"{filename}:{node.lineno}",
                            "confidence": 0.99,
                        }
                    )
    except SyntaxError:
        pass

    return issues


def post_or_update_pr_comment(repo_full: str, pr_number: int, body: str, token: str):
    """Post or update the debt risk comment using the invisible marker."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # 1. Look for existing comment
    comments_url = f"{GITHUB_API}/repos/{repo_full}/issues/{pr_number}/comments"
    resp = requests.get(comments_url, headers=headers)
    resp.raise_for_status()
    comments = resp.json()

    existing_comment_id = None
    for c in comments:
        if MARKER in c.get("body", ""):
            existing_comment_id = c["id"]
            break

    # Include marker in body
    final_body = f"{body}\n\n{MARKER}"

    # 2. Post or Update
    if existing_comment_id:
        update_url = (
            f"{GITHUB_API}/repos/{repo_full}/issues/comments/{existing_comment_id}"
        )
        update_resp = requests.patch(
            update_url, headers=headers, json={"body": final_body}
        )
        update_resp.raise_for_status()
        logger.info(
            f"Updated existing PR comment {existing_comment_id} for {repo_full}#{pr_number}"
        )
    else:
        post_resp = requests.post(
            comments_url, headers=headers, json={"body": final_body}
        )
        post_resp.raise_for_status()
        logger.info(f"Posted new PR comment for {repo_full}#{pr_number}")


@celery_app.task(name="workers.pr_tasks.process_pr_event")
def process_pr_event(repo_full: str, pr_number: int, token: str):
    """
    Background job to analyze PRs:
    1. Fetch diff
    2. Extract added lines
    3. Run DebtDetectionAgent
    4. Compute Risk Score
    5. Update comment
    6. Run safe auto-fixes
    """
    logger.info(f"Starting PR analysis for {repo_full}#{pr_number}")
    headers = {
        "Authorization": f"token {token}",
        # Request standard JSON for PR details (to get base branch)
        "Accept": "application/vnd.github+json",
    }

    # Get PR details to check base branch
    pr_resp = requests.get(
        f"{GITHUB_API}/repos/{repo_full}/pulls/{pr_number}", headers=headers
    )
    pr_resp.raise_for_status()
    pr_data = pr_resp.json()
    base_branch = pr_data.get("base", {}).get("ref", "")

    # Get diff
    diff_headers = headers.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    diff_resp = requests.get(
        f"{GITHUB_API}/repos/{repo_full}/pulls/{pr_number}", headers=diff_headers
    )
    diff_resp.raise_for_status()
    diff_text = diff_resp.text

    total_diff_lines = 0
    all_issues = []

    # Naive split by "diff --git " to separate files in the patch
    file_diffs = diff_text.split("diff --git ")
    for fd in file_diffs[1:]:
        lines = fd.split("\n")
        # Extract filename from "a/file.py b/file.py"
        header = lines[0]
        if not header.endswith(".py"):
            continue

        parts = header.split(" b/")
        filename = parts[-1] if len(parts) > 1 else header

        added_content = extract_added_lines(fd)
        if not added_content.strip():
            continue

        total_diff_lines += len(added_content.split("\n"))

        file_info = {"name": filename, "content": added_content}
        issues = _analyze_content(file_info)
        all_issues.extend(issues)

    # Compute score
    critical_cnt = sum(1 for i in all_issues if i.get("severity") == "CRITICAL")
    high_cnt = sum(1 for i in all_issues if i.get("severity") == "HIGH")
    medium_cnt = sum(1 for i in all_issues if i.get("severity") == "MEDIUM")
    low_cnt = sum(1 for i in all_issues if i.get("severity") == "LOW")

    score = min(100, critical_cnt * 40 + high_cnt * 20 + medium_cnt * 10 + low_cnt * 5)

    logger.info(
        f"{repo_full}#{pr_number} Risk Score: {score} (CRIT:{critical_cnt} HIGH:{high_cnt} MED:{medium_cnt} LOW:{low_cnt})"
    )

    # ── Persist lightweight Scan record ────────────────────────────────
    scan_id = None
    try:
        from database import SyncSessionLocal
        from sqlalchemy import select
        from models.db_models import Project, Scan

        db = SyncSessionLocal()
        try:
            repo_url = f"https://github.com/{repo_full}"
            project = db.execute(
                select(Project).where(Project.repo_url == repo_url)
            ).scalar_one_or_none()

            if project:
                # Check for existing PR scan (upsert)
                existing = db.execute(
                    select(Scan).where(
                        Scan.project_id == project.id,
                        Scan.pr_number == pr_number,
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.debt_score = score
                    existing.detection_results = {"issues": [i for i in all_issues]}
                    existing.summary = {
                        "critical": critical_cnt,
                        "high": high_cnt,
                        "medium": medium_cnt,
                        "low": low_cnt,
                        "total_issues": len(all_issues),
                        "tokens_input": 0,
                        "tokens_output": 0,
                        "model_usage": {"groq": 0, "gemini": 0},
                    }
                    existing.status = "completed"
                    existing.completed_at = datetime.now(timezone.utc)
                    scan_id = str(existing.id)
                else:
                    scan_record = Scan(
                        project_id=project.id,
                        scan_type="pr",
                        pr_number=pr_number,
                        debt_score=score,
                        status="completed",
                        branch=base_branch or "unknown",
                        summary={
                            "critical": critical_cnt,
                            "high": high_cnt,
                            "medium": medium_cnt,
                            "low": low_cnt,
                            "total_issues": len(all_issues),
                            "tokens_input": 0,
                            "tokens_output": 0,
                            "model_usage": {"groq": 0, "gemini": 0},
                        },
                        detection_results={"issues": [i for i in all_issues]},
                        completed_at=datetime.now(timezone.utc),
                    )
                    db.add(scan_record)
                    db.flush()
                    scan_id = str(scan_record.id)

                db.commit()
                logger.info(
                    f"PR scan record saved: {scan_id} for {repo_full}#{pr_number}"
                )
            else:
                logger.info(f"No project found for {repo_url} — PR scan not persisted")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to persist PR scan record: {e}")

    # Use real scan_id if available, else generate one for the comment link
    if not scan_id:
        scan_id = str(uuid.uuid4())[:12]

    if score > 25:
        COST_MAP = {
            "hardcoded_password": 106.25,
            "hardcoded_api_key": 106.25,
            "bare_except": 63.75,
            "long_method": 297.50,
            "unpinned_dependencies": 85.00,
        }

        # Group issues for table
        issue_summary = {}
        for issue in all_issues:
            itype = issue.get("type", "unknown")
            sev = issue.get("severity", "MEDIUM")
            cost = COST_MAP.get(itype, 42.50)
            if itype not in issue_summary:
                issue_summary[itype] = {"severity": sev, "count": 0, "cost": 0.0}
            issue_summary[itype]["count"] += 1
            issue_summary[itype]["cost"] += cost

        rows = []
        for itype, data in issue_summary.items():
            rows.append(f"| {itype} | {data['severity']} | ${data['cost']:.0f} |")

        table_content = "\n".join(rows) if rows else "| No major debt | | $0 |"

        body = f"""## 🤖 CodeDebt Guardian

**Debt Risk Score: {score}/100**

| Issue Type | Severity | Est Cost |
|------------|----------|----------|
{table_content}

⚠️ Review recommended before merge.

---

View full report:
https://codedebt-guardian.app/scans/{scan_id}"""

        post_or_update_pr_comment(repo_full, pr_number, body, token)

    # Run auto-fixes
    for issue in all_issues:
        should_fix = (
            issue.get("type", "") in SAFE_AUTO_FIX_TYPES
            and issue.get("confidence", 0) >= 0.90
            and total_diff_lines < 50
            and base_branch not in ("main", "master", "production")
        )
        if should_fix:
            try:
                from tools.pr_generator import PRGenerator

                pr_gen = PRGenerator(token=token)
                repo_url_full = f"https://github.com/{repo_full}"
                fix_proposal = {
                    "fix_summary": f"Auto-fix {issue['type']}",
                    "before_code": "",
                    "after_code": "",
                    "steps": [
                        f"Fix {issue['type']} at {issue.get('location', 'unknown')}"
                    ],
                }
                auto_pr = pr_gen.create_fix_pr(
                    repo_url=repo_url_full,
                    fix_proposal=fix_proposal,
                    issue=issue,
                    base_branch=base_branch,
                )
                if auto_pr:
                    logger.info(f"Auto-fix PR created: {auto_pr.get('html_url')}")
            except Exception as e:
                logger.warning(f"Auto-fix failed for {issue.get('type')}: {e}")

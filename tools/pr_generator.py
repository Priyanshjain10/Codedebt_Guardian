"""
PR Generator Tool - Automatically creates GitHub Pull Requests with debt fixes applied.

This is the "wow factor" feature:
Instead of just SHOWING a fix, it actually OPENS a real PR on GitHub with the code changed.

Flow:
1. Fork or branch the repo
2. Apply the fix to the actual file
3. Commit the change
4. Open a PR with a detailed description
"""

import os
import re
import base64
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)
GITHUB_API_BASE = "https://api.github.com"


class PRGenerator:
    """
    Autonomously creates GitHub Pull Requests with debt fixes applied.

    This is what separates CodeDebt Guardian from every other "detector" tool.
    It doesn't just find problems — it fixes them, autonomously.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN or token argument is required for PR generation"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {self.token}",
                "User-Agent": "CodeDebt-Guardian/1.0",
            }
        )
        # Get authenticated user info
        self._username = self._get_username()

    def _get_username(self) -> str:
        """Get the authenticated GitHub username."""
        try:
            resp = self.session.get(f"{GITHUB_API_BASE}/user", timeout=10)
            resp.raise_for_status()
            return resp.json()["login"]
        except Exception as e:
            logger.warning(f"Could not get GitHub username: {e}")
            return "codedebt-guardian"

    def create_fix_pr(
        self,
        repo_url: str,
        fix_proposal: Dict[str, Any],
        issue: Dict[str, Any],
        base_branch: str = "main",
        scan_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub PR applying a fix proposal to the actual codebase.

        Args:
            repo_url: GitHub repo URL (e.g. https://github.com/owner/repo)
            fix_proposal: Fix proposal from FixProposalAgent
            issue: The original detected issue
            base_branch: Branch to base the PR on

        Returns:
            PR info dict with url, number, title, etc.
        """
        owner, repo = self._parse_url(repo_url)
        issue_type = issue.get("type", "unknown")
        location = issue.get("location", "")

        logger.info(f"Creating PR for {issue_type} in {owner}/{repo}")

        # Fetch actual default branch from GitHub API
        try:
            repo_info = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers={"Authorization": f"token {self.token}"},
                timeout=10,
            ).json()
            base_branch = repo_info.get("default_branch", base_branch)
        except Exception:
            pass  # keep the passed-in default

        # Step 1: Get the file content to patch
        file_path = self._extract_file_path(location)
        if not file_path:
            logger.warning(f"Cannot determine file path from location: {location}")
            return self._create_documentation_pr(
                owner, repo, fix_proposal, issue, base_branch
            )

        # Step 2: Create a new branch
        branch_name = self._make_branch_name(issue_type, file_path)
        base_sha = self._get_branch_sha(owner, repo, base_branch)
        if not base_sha:
            return None

        branch_created = self._create_branch(owner, repo, branch_name, base_sha)
        if not branch_created:
            return None

        # Step 3: Get current file content
        file_content, file_sha = self._get_file(owner, repo, file_path, base_branch)
        if file_content is None:
            return self._create_documentation_pr(
                owner, repo, fix_proposal, issue, base_branch
            )

        # Step 4: Apply the fix
        patched_content = self._apply_fix(file_content, fix_proposal, issue)
        if patched_content == file_content:
            logger.info(f"No changes detected for {issue_type} — skipping PR creation")
            return None

        # Step 5: Commit the patched file
        commit_msg = self._make_commit_message(issue_type, file_path, fix_proposal)
        committed = self._commit_file(
            owner, repo, file_path, patched_content, file_sha, branch_name, commit_msg
        )
        if not committed:
            return None

        # Step 6: Open the Pull Request
        pr_title = self._make_pr_title(issue_type, fix_proposal)
        pr_body = self._make_pr_body(fix_proposal, issue, scan_id=scan_id)

        try:
            return self._open_pr(
                owner, repo, branch_name, base_branch, pr_title, pr_body
            )
        except Exception as e:
            logger.error(f"Failed to open PR for {repo_url}: {e}")
            return None

    def create_batch_prs(
        self,
        repo_url: str,
        fix_proposals: List[Dict],
        ranked_issues: List[Dict],
        max_prs: int = 3,
        base_branch: str = "main",
        scan_id: str = "",
    ) -> List[Dict]:
        """
        Create multiple PRs for the top-priority fixes.

        Args:
            repo_url: GitHub repo URL
            fix_proposals: List of fix proposals from FixProposalAgent
            ranked_issues: Ranked issues from PriorityRankingAgent
            max_prs: Max number of PRs to create (default 3 to avoid spam)
            base_branch: Base branch for PRs

        Returns:
            List of created PR info dicts
        """
        created_prs = []
        issue_map = {i.get("_rank_id"): i for i in ranked_issues}

        # Only create PRs for quick wins and critical issues
        priority_fixes = [
            f
            for f in fix_proposals
            if issue_map.get(f.get("issue_id"), {}).get("priority")
            in ["CRITICAL", "HIGH"]
            or issue_map.get(f.get("issue_id"), {}).get("quick_win")
        ][:max_prs]

        for fix in priority_fixes:
            issue = issue_map.get(fix.get("issue_id"), {})
            try:
                pr = self.create_fix_pr(
                    repo_url, fix, issue, base_branch=base_branch, scan_id=scan_id
                )
                if pr:
                    created_prs.append(pr)
                    logger.info(f"Created PR #{pr.get('number')}: {pr.get('html_url')}")
                time.sleep(1)  # Be polite to GitHub API
            except Exception as e:
                logger.warning(f"Failed to create PR for {fix.get('issue_type')}: {e}")

        return created_prs

    # ── Internal helpers ───────────────────────────────────────────────────────

    # Issue types we can fix with pure code — no AI needed
    FIXABLE_TYPES = {
        "hardcoded_password",
        "hardcoded_api_key",
        "hardcoded_token",
        "bare_except",
        "unpinned_dependencies",
    }
    # Issue types we cannot safely auto-fix — skip PR creation entirely
    UNFIXABLE_TYPES = {
        "long_method",
        "god_class",
        "too_many_parameters",
        "missing_docstring",
        "satd_defect",
        "satd_design",
    }

    def _apply_fix(self, file_content: str, fix_proposal: Dict, issue: Dict) -> str:
        """
        Apply the fix using pure code replacement — no AI, no Gemini, no quota.
        Returns original content unchanged for unfixable types (caller will skip PR).
        """
        import ast as _ast

        issue_type = issue.get("type", "")

        # Hard skip — never attempt to fix these
        if issue_type in self.UNFIXABLE_TYPES:
            return file_content

        if issue_type == "unpinned_dependencies":
            return self._fix_unpinned_deps(file_content, issue)
        if issue_type == "bare_except":
            return self._fix_bare_except(file_content, issue)
        if issue_type in ("hardcoded_password", "hardcoded_api_key", "hardcoded_token"):
            return self._fix_hardcoded_cred(file_content, issue)

        # For any other type try direct string replacement only
        before_code = fix_proposal.get("before_code", "").strip()
        after_code = fix_proposal.get("after_code", "").strip()

        if not before_code or not after_code:
            return file_content

        if before_code in file_content:
            patched = file_content.replace(before_code, after_code, 1)
            try:
                _ast.parse(patched)
            except SyntaxError as e:
                logger.warning(f"Patched code has syntax error ({e}), keeping original")
                return file_content
            return patched

        # Cannot apply fix — return unchanged (caller will skip PR)
        return file_content

    def _ai_apply_fix(self, file_content: str, fix_proposal: Dict, issue: Dict) -> str:
        """Use Gemini to rewrite the relevant file content when string replacement fails."""
        try:
            import google.generativeai as genai

            if not os.environ.get("GOOGLE_API_KEY"):
                logger.warning("GOOGLE_API_KEY not set, cannot use Gemini fallback")
                return file_content

            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = f"""You are fixing a technical debt issue in a source file.
Issue:
Type: {issue.get("type", "")}
Description: {issue.get("description", "")}
Location: {issue.get("location", "")}

Proposed Fix:
{fix_proposal.get("fix_summary", "")}
Before code to look for:
{fix_proposal.get("before_code", "")}
After code to replace with:
{fix_proposal.get("after_code", "")}

Here is the original file content:
{file_content}

Return ONLY the complete updated file content. 
No markdown, no backticks, no explanation. Change only the minimum necessary to fix the described issue."""

            response = model.generate_content(prompt)
            patched = response.text

            # Remove markdown blocks if present despite instructions
            if patched.startswith("```"):
                patched = patched.split("\n", 1)[1]
                if patched.endswith("```"):
                    patched = patched.rsplit("```", 1)[0]
                elif patched.endswith("```\n"):
                    patched = patched.rsplit("```\n", 1)[0]

            patched = patched.strip()

            if not patched:
                raise ValueError("Gemini returned empty string")

            after_code = fix_proposal.get("after_code", "").strip()
            before_code = fix_proposal.get("before_code", "").strip()

            if after_code and after_code not in patched:
                raise ValueError("Gemini output does not contain the fixed code")
            if before_code and before_code in patched:
                raise ValueError(
                    "Gemini output still contains the original bad pattern"
                )

            # Syntax validation
            import ast as _ast

            _ast.parse(patched)

            return patched

        except Exception as e:
            logger.error(f"AI apply fix failed: {e}")
            if "Gemini returned empty string" in str(e) or "Gemini output" in str(e):
                raise ValueError(str(e))
            return file_content

    def _fix_unpinned_deps(self, content: str, issue: Dict) -> str:
        """Pin all unpinned dependencies in requirements.txt"""
        import re

        lines = content.split("\n")
        patched = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                # If package has no version pin, add >=current
                if re.match(r"^[a-zA-Z0-9_\-]+$", stripped):
                    line = f"{stripped}>=0.0.1  # TODO: pin to specific version"
            patched.append(line)
        if "import os" not in content and patched != lines:
            pass  # no os import needed here
        return "\n".join(patched)

    def _fix_bare_except(self, content: str, issue: Dict) -> str:
        """Replace bare except: with except Exception:"""
        import re

        location = issue.get("location", "")
        try:
            line_num = int(location.split(":")[-1]) - 1
        except (ValueError, IndexError):
            line_num = None

        lines = content.split("\n")
        if line_num is not None and 0 <= line_num < len(lines):
            line = lines[line_num]
            if re.match(r"\s*except\s*:", line):
                lines[line_num] = line.replace("except:", "except Exception:")
                return "\n".join(lines)

        # Fallback: replace all bare excepts
        return re.sub(r"(\s*)except\s*:", r"\1except Exception:", content)

    def _fix_hardcoded_cred(self, content: str, issue: Dict) -> str:
        """Replace hardcoded credential with os.environ.get() call."""
        import re

        location = issue.get("location", "")
        try:
            line_num = int(location.split(":")[-1]) - 1
        except (ValueError, IndexError):
            return content

        lines = content.split("\n")
        if 0 <= line_num < len(lines):
            line = lines[line_num]
            # Extract variable name
            match = re.match(r'(\s*)(\w+)\s*=\s*["\'][^"\']+["\']', line)
            if match:
                indent = match.group(1)
                var_name = match.group(2)
                lines[line_num] = (
                    f'{indent}{var_name} = os.environ.get("{var_name.upper()}")  # TODO: Set in .env'
                )
                # Add import if not present
                if "import os" not in content:
                    lines.insert(0, "import os")
                return "\n".join(lines)

        return content

    def _create_documentation_pr(
        self, owner: str, repo: str, fix_proposal: Dict, issue: Dict, base_branch: str
    ) -> Optional[Dict]:
        """
        When we can't directly patch the code, create a PR that adds a
        TECH_DEBT.md file documenting the issue and fix instructions.
        """
        branch_name = f"codedebt/add-debt-docs-{uuid.uuid4().hex[:8]}"
        base_sha = self._get_branch_sha(owner, repo, base_branch)
        if not base_sha:
            return None

        if not self._create_branch(owner, repo, branch_name, base_sha):
            return None

        # Create TECH_DEBT.md content
        md_content = self._make_debt_doc(fix_proposal, issue)

        # Check if TECH_DEBT.md already exists
        existing_content, existing_sha = self._get_file(
            owner, repo, "TECH_DEBT.md", base_branch
        )
        if existing_content:
            md_content = existing_content + "\n\n---\n\n" + md_content

        committed = self._commit_file(
            owner,
            repo,
            "TECH_DEBT.md",
            md_content,
            existing_sha,
            branch_name,
            f"docs: document technical debt - {issue.get('type', 'unknown')} [{issue.get('severity', '')}]",
        )
        if not committed:
            return None

        pr_title = f"📋 docs: Document {issue.get('type', 'debt')} technical debt ({issue.get('severity', '')})"
        pr_body = self._make_pr_body(fix_proposal, issue)
        return self._open_pr(owner, repo, branch_name, base_branch, pr_title, pr_body)

    def _make_debt_doc(self, fix: Dict, issue: Dict) -> str:
        """Generate TECH_DEBT.md content for a single issue."""
        steps_text = "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(fix.get("steps", []))
        )
        return f"""## 🔴 {issue.get("type", "Technical Debt").replace("_", " ").title()} [{issue.get("severity", "UNKNOWN")}]

**Location:** `{issue.get("location", "Unknown")}`
**Priority Score:** {issue.get("score", "N/A")}
**Effort to Fix:** {issue.get("effort_to_fix", "Unknown")}

### Problem
{fix.get("problem_summary", issue.get("description", "See issue for details"))}

### Fix
{fix.get("fix_summary", "See fix proposal for details")}

### Steps
{steps_text}

### Testing
{fix.get("testing_tip", "Run your test suite after applying the fix.")}

*Generated by [CodeDebt Guardian](https://github.com/Priyanshjain10/codedebt-guardian) 🤖*
"""

    def _make_pr_body(self, fix: Dict, issue: Dict, scan_id: str = "") -> str:
        """Generate a detailed PR description."""
        import difflib

        _default_steps = (
            "- [ ] Review the changes\n- [ ] Run tests\n- [ ] Approve if correct"
        )
        steps_md = (
            "\n".join("- [ ] " + step for step in fix.get("steps", []))
            or _default_steps
        )
        checklist = steps_md
        refs_md = "\n".join("- " + ref for ref in fix.get("references", []))

        before_code = fix.get("before_code", "")
        after_code = fix.get("after_code", "")
        if before_code and after_code:
            diff_lines = list(
                difflib.unified_diff(
                    before_code.splitlines(keepends=True),
                    after_code.splitlines(keepends=True),
                    fromfile="BEFORE",
                    tofile="AFTER",
                )
            )
            diff_text = "".join(diff_lines)
            diff_md = f"```diff\n{diff_text}\n```" if diff_text else ""
        else:
            diff_md = ""

        return f"""## 🤖 Automated Fix by CodeDebt Guardian

> This PR was automatically generated by [CodeDebt Guardian](https://github.com/Priyanshjain10/codedebt-guardian), an AI-powered technical debt detection and remediation system.

---

### 🔍 Issue Detected
| Field | Value |
|-------|-------|
| **Type** | `{issue.get("type", "unknown")}` |
| **Severity** | **{issue.get("severity", "UNKNOWN")}** |
| **Location** | `{issue.get("location", "Unknown")}` |
| **Priority Score** | {issue.get("score", "N/A")}/100 |
| **Estimated Fix Time** | {fix.get("estimated_time", issue.get("effort_to_fix", "Unknown"))} |

### ❌ Problem
{fix.get("problem_summary", issue.get("description", "Technical debt detected"))}

**Impact:** {issue.get("impact", "Reduces code quality and maintainability")}

### ✅ Fix Applied
{fix.get("fix_summary", "See changes above")}

{diff_md}

### 📋 Review Checklist
{checklist}

### 🧪 Testing
{fix.get("testing_tip", "Run your test suite to verify no regressions.")}

### 📚 References
{refs_md if refs_md else "- No references provided"}

---

{"[View Full Scan Report on CodeDebt Guardian](https://app.codedebt.dev/scans/" + scan_id + ")" if scan_id else "Opened automatically by CodeDebt Guardian"}
*⭐ If this helped, please star the repo!*
"""

    def _make_pr_title(self, issue_type: str, fix: Dict) -> str:
        summary = fix.get("fix_summary", "")[:50]
        return f"fix({issue_type}): [CodeDebt Guardian] {summary}"

    def _make_commit_message(self, issue_type: str, file_path: str, fix: Dict) -> str:
        return (
            f"fix: resolve {issue_type.replace('_', '-')} in {file_path}\n\n"
            f"{fix.get('fix_summary', 'Automated debt fix')}\n\n"
            f"Generated by CodeDebt Guardian 🤖"
        )

    def _make_branch_name(self, issue_type: str, file_path: str) -> str:
        safe_type = re.sub(r"[^a-z0-9-]", "-", issue_type.lower())
        uid = uuid.uuid4().hex[:8]
        return f"codedebt/fix-{safe_type}-{uid}"

    def _extract_file_path(self, location: str) -> Optional[str]:
        """Extract file path from 'path/to/file.py:line_num' format."""
        if not location:
            return None
        path = location.split(":")[0]
        if path.endswith(".py") or path.endswith(".js") or path.endswith(".ts"):
            return path
        return None

    def _parse_url(self, repo_url: str) -> tuple:
        match = re.search(
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url.rstrip("/")
        )
        if match:
            return match.group(1), match.group(2)
        raise ValueError(f"Cannot parse repo URL: {repo_url}")

    def _get_branch_sha(self, owner: str, repo: str, branch: str) -> Optional[str]:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{branch}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()["object"]["sha"]
        except Exception as e:
            logger.error(f"Cannot get SHA for branch {branch}: {e}")
            return None

    def _create_branch(self, owner: str, repo: str, branch: str, sha: str) -> bool:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs"
        try:
            resp = self.session.post(
                url, json={"ref": f"refs/heads/{branch}", "sha": sha}, timeout=10
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Cannot create branch {branch}: {e}")
            return False

    def _get_file(self, owner: str, repo: str, path: str, branch: str) -> tuple:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 404:
                return None, None
            resp.raise_for_status()
            data = resp.json()
            content = base64.b64decode(data["content"]).decode(
                "utf-8", errors="replace"
            )
            return content, data["sha"]
        except Exception as e:
            logger.warning(f"Cannot get file {path}: {e}")
            return None, None

    def _commit_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        file_sha: Optional[str],
        branch: str,
        message: str,
    ) -> bool:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if file_sha:
            payload["sha"] = file_sha
        try:
            resp = self.session.put(url, json=payload, timeout=15)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Cannot commit {path}: {e}")
            return False

    def _open_pr(
        self, owner: str, repo: str, head: str, base: str, title: str, body: str
    ) -> Optional[Dict]:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        try:
            resp = self.session.post(
                url,
                json={
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                    "draft": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "number": data["number"],
                "title": data["title"],
                "html_url": data["html_url"],
                "state": data["state"],
                "branch": head,
            }
        except Exception as e:
            logger.error(f"Cannot open PR: {e}")
            return None

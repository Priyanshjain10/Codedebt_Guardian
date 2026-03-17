"""Change Detector — finds only files changed since last analysis run."""

import logging
import os
import requests
import base64
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ChangeDetector:
    SKIP_PATTERNS = ["test_", "_test.py", "tests/", "migrations/", "setup.py"]

    def __init__(self):
        self._last_sha: dict = {}
        try:
            from tools.persistent_memory import PersistentMemoryBank

            self._memory = PersistentMemoryBank()
        except Exception:
            self._memory = None

    def _get_last_sha(self, owner: str, repo: str) -> str:
        key = f"last_sha:{owner}/{repo}"
        if self._memory:
            try:
                cached = self._memory.get(key)
                if cached:
                    return cached
            except Exception:
                pass
        return self._last_sha.get(key, "")

    def _save_last_sha(self, owner: str, repo: str, sha: str):
        key = f"last_sha:{owner}/{repo}"
        self._last_sha[key] = sha
        if self._memory:
            try:
                self._memory.set(key, sha, ttl_seconds=86400 * 7)
            except Exception:
                pass

    def get_changed_files(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Returns files changed since the last time this ran.
        On first run: returns files from the last 24 hours of commits.
        On subsequent runs: returns only files changed since last SHA.
        """
        try:
            token = os.environ.get("GITHUB_TOKEN", "")
            headers = {"Authorization": f"token {token}"} if token else {}

            # Get recent commits (up to 20)
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                params={"per_page": 20},
                headers=headers,
                timeout=10,
            )
            if r.status_code != 200:
                logger.error(f"GitHub API error: {r.status_code}")
                return []

            commits = r.json()
            if not commits:
                return []

            latest_sha = commits[0]["sha"]
            last_sha = self._get_last_sha(owner, repo)

            # Find commits since last run
            if last_sha:
                new_commits = []
                for c in commits:
                    if c["sha"] == last_sha:
                        break
                    new_commits.append(c["sha"])
                if not new_commits:
                    logger.info("No new commits since last run")
                    self._save_last_sha(owner, repo, latest_sha)
                    return []
                logger.info(f"Found {len(new_commits)} new commits since last run")
            else:
                # First run — only check latest commit
                new_commits = [latest_sha]
                logger.info("First run — analyzing latest commit")

            # Collect unique changed files across all new commits
            changed_files: Dict[str, Dict] = {}
            for sha in new_commits[:10]:  # max 10 commits
                r = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
                    headers=headers,
                    timeout=10,
                )
                if r.status_code != 200:
                    continue
                for f in r.json().get("files", []):
                    if self._should_analyze(f):
                        # Later commits win (more recent)
                        changed_files[f["filename"]] = f

            # Fetch content for each changed file
            result = []
            for filename, f in list(changed_files.items())[:15]:
                r2 = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}",
                    headers=headers,
                    timeout=10,
                )
                if r2.status_code == 200:
                    try:
                        content = base64.b64decode(r2.json()["content"]).decode(
                            "utf-8", errors="ignore"
                        )
                        result.append(
                            {
                                "name": filename.split("/")[-1],
                                "path": filename,
                                "content": content,
                                "additions": f.get("additions", 0),
                                "changes": f.get("changes", 0),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Could not decode {filename}: {e}")

            # Save latest SHA for next run
            self._save_last_sha(owner, repo, latest_sha)
            logger.info(f"Incremental: {len(result)} changed files to analyze")
            return result

        except Exception as e:
            logger.error(f"Change detection failed: {e}")
            return []

    def _should_analyze(self, f: Dict) -> bool:
        name = f.get("filename", "")
        if not name.endswith(".py"):
            return False
        if f.get("status") == "removed":
            return False
        return not any(p in name for p in self.SKIP_PATTERNS)

    def get_summary(self, owner: str, repo: str) -> Dict[str, Any]:
        """Returns a summary of what changed — useful for logging."""
        last_sha = self._get_last_sha(owner, repo)
        return {
            "last_analyzed_sha": last_sha[:8] if last_sha else "never",
            "is_first_run": not bool(last_sha),
        }

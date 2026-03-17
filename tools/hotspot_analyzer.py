"""
Hotspot Analyzer - finds files that are BOTH complex AND frequently changed.
This is where technical debt hurts most.
Inspired by CodeScene's research on code hotspots.
"""

import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class HotspotAnalyzer:
    """
    Combines code complexity with change frequency to find danger zones.

    A file touched 50 times that is also complex = hotspot.
    A complex file nobody touches = low priority.
    A simple file touched constantly = not a hotspot.
    """

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}

    def analyze(self, issues: List[Dict]) -> List[Dict]:
        """
        Score each file based on issue counts and severity.
        Score = (critical * 3) + (high * 2) + (medium * 1)
        """
        file_counts = {}
        for issue in issues:
            filepath = issue.get("location", "").split(":")[0]
            if not filepath:
                continue
            if filepath not in file_counts:
                file_counts[filepath] = {"critical": 0, "high": 0, "medium": 0}

            sev = issue.get("severity", "LOW").upper()
            if sev == "CRITICAL":
                file_counts[filepath]["critical"] += 1
            elif sev == "HIGH":
                file_counts[filepath]["high"] += 1
            elif sev == "MEDIUM":
                file_counts[filepath]["medium"] += 1

        results = []
        for filepath, counts in file_counts.items():
            score = (
                (counts["critical"] * 3) + (counts["high"] * 2) + (counts["medium"] * 1)
            )
            if score > 0:
                results.append(
                    {
                        "filepath": filepath,
                        "hotspot_score": score,
                        "complexity_score": score,
                        "churn_score": 1,
                        "commits_90d": 1,
                        "unique_authors": 1,
                        "last_modified_days": 1,
                        "danger_level": self._danger_level(score),
                        "recommendation": self._recommendation(score, counts),
                    }
                )

        return sorted(results, key=lambda x: x["hotspot_score"], reverse=True)

    def _danger_level(self, score: float) -> str:
        if score >= 10:
            return "CRITICAL"
        if score >= 5:
            return "HIGH"
        if score >= 2:
            return "MEDIUM"
        return "LOW"

    def _recommendation(self, score: float, counts: Dict) -> str:
        total = sum(counts.values())
        if score >= 10:
            return f"Critical hotspot — {total} issues ({counts['critical']} CRITICAL). Refactor immediately."
        if score >= 5:
            return f"High-risk file — {total} issues. Schedule refactoring this sprint."
        if score >= 2:
            return "Monitor closely — active file with growing issues."
        return "Low risk — relatively clean file."

    def knowledge_silos(self, owner: str, repo: str, files: List[Dict]) -> List[Dict]:
        """
        Detect files where only ONE developer has made commits in last 6 months.
        If that person leaves, nobody understands this code.
        """
        silos = []
        since = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()

        for file_info in files[:20]:
            filepath = file_info.get("path", file_info.get("name", ""))
            if not filepath:
                continue
            try:
                r = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits",
                    params={"path": filepath, "since": since, "per_page": 100},
                    headers=self.headers,
                    timeout=10,
                )
                commits = r.json() if r.status_code == 200 else []
                authors = {}
                for c in commits:
                    try:
                        email = c["commit"]["author"]["email"]
                        name = c["commit"]["author"]["name"]
                        authors[email] = name
                    except Exception:
                        pass

                if len(authors) == 1:
                    sole_author = list(authors.values())[0]
                    silos.append(
                        {
                            "filepath": filepath,
                            "sole_author": sole_author,
                            "commits_6mo": len(commits),
                            "risk": "HIGH" if len(commits) > 5 else "MEDIUM",
                            "warning": (
                                f"{sole_author} is the only person who "
                                f"touched this file in 6 months ({len(commits)} commits). "
                                f"Bus factor: 1"
                            ),
                        }
                    )
            except Exception as e:
                logger.warning(f"Silo check failed for {filepath}: {e}")

        return sorted(silos, key=lambda x: x["commits_6mo"], reverse=True)

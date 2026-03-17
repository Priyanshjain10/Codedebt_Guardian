"""
Debt Interest Calculator — calculates the TRUE cost of ignoring technical debt.
Uses GitHub commit history to show how debt compounds over time.
No other tool does this.
"""

import logging
import os
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

HOURLY_RATE_USD = float(
    os.environ.get("DEVELOPER_HOURLY_RATE", "85")
)  # Industry standard senior dev rate (Stack Overflow survey 2024)


class DebtInterestCalculator:
    """
    Calculates compound interest on technical debt using real git history.
    Shows: age, touch frequency, cost now vs cost later.
    """

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.headers = {"Authorization": f"token {self.token}"} if self.token else {}

    def calculate(
        self, owner: str, repo: str, filepath: str, issue: Dict
    ) -> Dict[str, Any]:
        """
        Calculate full debt interest report for a single issue.
        Returns cost breakdown with real git data.
        """
        commits = self._get_file_commits(owner, repo, filepath)
        age_days = self._calculate_age(commits)
        touch_count = len(commits)
        authors = self._unique_authors(commits)
        monthly_touches = round(touch_count / max(age_days / 30, 1), 1)

        base_hours = self._base_fix_hours(
            issue.get("effort_to_fix", "HOURS"), issue.get("type", "")
        )
        complexity_multiplier = self._complexity_multiplier(age_days, touch_count)
        current_cost_hours = round(base_hours * complexity_multiplier, 1)
        future_cost_hours = round(
            current_cost_hours * 1.23, 1
        )  # 23% harder each quarter

        current_cost_usd = round(current_cost_hours * HOURLY_RATE_USD, 0)
        future_cost_usd = round(future_cost_hours * HOURLY_RATE_USD, 0)

        interest_rate = round((complexity_multiplier - 1) * 100, 1)

        return {
            "filepath": filepath,
            "issue_type": issue.get("type", "unknown"),
            "severity": issue.get("severity", "MEDIUM"),
            # Git history data
            "age_days": age_days,
            "total_touches": touch_count,
            "unique_authors": len(authors),
            "monthly_touch_rate": monthly_touches,
            # Cost analysis
            "base_fix_hours": base_hours,
            "complexity_multiplier": complexity_multiplier,
            "current_fix_hours": current_cost_hours,
            "future_fix_hours": future_cost_hours,
            "current_cost_usd": current_cost_usd,
            "future_cost_usd": future_cost_usd,
            "interest_rate_pct": interest_rate,
            # Human readable summary
            "summary": self._generate_summary(
                issue,
                age_days,
                touch_count,
                current_cost_hours,
                current_cost_usd,
                future_cost_usd,
                interest_rate,
            ),
        }

    def calculate_repo_total(
        self, owner: str, repo: str, issues: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate total debt cost across all issues in a repo."""
        results = []
        total_current_usd = 0
        total_future_usd = 0

        for issue in issues[:20]:  # Cap at 20 for API limits
            filepath = issue.get("location", "").split(":")[0]
            if not filepath or not filepath.endswith(".py"):
                continue
            try:
                result = self.calculate(owner, repo, filepath, issue)
                results.append(result)
                total_current_usd += result["current_cost_usd"]
                total_future_usd += result["future_cost_usd"]
            except Exception as e:
                logger.warning(f"Could not calculate interest for {filepath}: {e}")

        return {
            "total_issues_analyzed": len(results),
            "total_current_cost_usd": round(total_current_usd, 0),
            "total_future_cost_usd": round(total_future_usd, 0),
            "potential_savings_usd": round(total_future_usd - total_current_usd, 0),
            "roi_message": f"Fix now and save ${round(total_future_usd - total_current_usd, 0):,.0f}",
            "issues": results,
        }

    def _get_file_commits(self, owner: str, repo: str, filepath: str) -> List[Dict]:
        """Get commit history for a specific file."""
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                params={"path": filepath, "per_page": 100},
                headers=self.headers,
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()
            return []
        except Exception as e:
            logger.error(f"Failed to get commits for {filepath}: {e}")
            return []

    def _calculate_age(self, commits: List[Dict]) -> int:
        """Calculate age of file in days from first commit."""
        if not commits:
            return 30  # Default assumption
        try:
            oldest = commits[-1]["commit"]["author"]["date"]
            oldest_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - oldest_dt).days
            return max(age, 1)
        except Exception:
            return 30

    def _unique_authors(self, commits: List[Dict]) -> set:
        """Get unique authors who touched this file."""
        authors = set()
        for c in commits:
            try:
                authors.add(c["commit"]["author"]["email"])
            except Exception:
                pass
        return authors

    def _base_fix_hours(self, effort: str, issue_type: str = "") -> float:
        """Convert effort level to hours using issue-type specific estimates."""
        type_hours = {
            "bare_except": 0.75,
            "hardcoded_password": 1.25,
            "missing_docstring": 0.35,
            "long_method": 3.50,
            "god_class": 9.50,
            "too_many_parameters": 1.75,
            "syntax_error": 0.45,
            "console_log": 0.20,
            "var_declaration": 0.30,
            "unhandled_promise": 1.10,
            "callback_hell": 4.25,
        }
        if issue_type in type_hours:
            return type_hours[issue_type]
        return {"MINUTES": 0.40, "HOURS": 1.75, "DAYS": 7.50}.get(effort, 1.75)

    def _complexity_multiplier(self, age_days: int, touch_count: int) -> float:
        """
        Calculate how much harder the fix has become over time.
        More touches = more entangled = harder to fix.
        """
        age_factor = 1.0 + (age_days / 365) * 0.5  # 50% harder per year
        touch_factor = 1.0 + (touch_count / 20) * 0.3  # 30% harder per 20 touches
        return round(min(age_factor * touch_factor, 4.0), 2)  # Cap at 4x

    def _generate_summary(
        self, issue, age_days, touches, hours, cost_usd, future_usd, interest_rate
    ) -> str:
        issue_type = issue.get("type", "debt").replace("_", " ")
        return (
            f"This {issue_type} is {age_days} days old, "
            f"touched {touches} times by {touches} commits. "
            f"Fix costs ~{hours}h (${cost_usd:,.0f}) today. "
            f"Wait one quarter and it costs ${future_usd:,.0f} "
            f"({interest_rate}% interest on your technical debt)."
        )

"""
Technical Debt Ratio (TDR) — single health score for your codebase.
Like a credit score, but for code. 0-100. Executives understand it instantly.
TDR = (remediation_cost / development_cost) * 100
Healthy: <5% | Warning: 5-20% | Critical: >20%
"""
from typing import Any, Dict, List, Optional
import os

class TDRCalculator:

    HOURLY_RATE = float(os.environ.get("DEVELOPER_HOURLY_RATE", "85"))
    LOC_PER_HOUR = 15        # industry average lines of production code per dev-hour
    AVG_LOC_PER_FILE = 120   # realistic average for a Python project file

    def calculate(
        self,
        issues: List[Dict],
        files_or_issues: Any = None,    # kept for backwards-compat, ignored
        files_scanned: int = 0,
    ) -> Dict[str, Any]:
        """
        Calculate TDR from issues list and optional files_scanned count.
        Does NOT make any API calls or file reads.
        """
        # Estimate total LOC from files_scanned count
        # If files_scanned not given, estimate from issues (roughly 4 files per issue)
        if files_scanned and files_scanned > 0:
            total_loc = files_scanned * self.AVG_LOC_PER_FILE
        else:
            estimated_files = max(len(issues) // 3, 5)
            total_loc = estimated_files * self.AVG_LOC_PER_FILE
        total_loc = max(total_loc, 300)

        dev_cost_usd = (total_loc / self.LOC_PER_HOUR) * self.HOURLY_RATE

        fix_hours = {
            "hardcoded_password": 1.25,
            "bare_except": 0.75,
            "long_method": 3.50,
            "god_class": 9.50,
            "missing_docstring": 0.35,
            "too_many_parameters": 1.75,
            "console_log": 0.20,
            "var_declaration": 0.30,
            "unhandled_promise": 1.10,
            "callback_hell": 4.25,
            "satd_defect": 1.00,
            "satd_design": 2.00,
            "unpinned_dependencies": 0.25,
        }
        remediation_cost = sum(
            fix_hours.get(i.get("type", ""), 1.75) * self.HOURLY_RATE
            for i in issues
        )

        tdr_pct = round((remediation_cost / max(dev_cost_usd, 1)) * 100, 1)
        tdr_pct = min(tdr_pct, 100)

        health_score = round(max(0, 100 - (tdr_pct * 3)), 1)

        if tdr_pct < 5:
            grade, status, color = "A", "Healthy", "#22c55e"
        elif tdr_pct < 10:
            grade, status, color = "B", "Acceptable", "#84cc16"
        elif tdr_pct < 20:
            grade, status, color = "C", "Warning", "#f59e0b"
        elif tdr_pct < 40:
            grade, status, color = "D", "Concerning", "#f97316"
        else:
            grade, status, color = "F", "Critical", "#ef4444"

        return {
            "tdr_percent": tdr_pct,
            "health_score": health_score,
            "grade": grade,
            "status": status,
            "color": color,
            "total_loc": total_loc,
            "dev_cost_usd": round(dev_cost_usd),
            "remediation_cost_usd": round(remediation_cost),
            "interpretation": (
                f"Your codebase has a TDR of {tdr_pct}% — "
                f"for every $100 spent building this software, "
                f"${tdr_pct:.0f} is needed to fix existing debt. "
                f"Industry healthy threshold: <5%."
            )
        }

"""
CTO Report Generator — translates technical debt into business language.
Produces a boardroom-ready HTML report for non-technical executives.
No other tool does this.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class CTOReportGenerator:
    """
    Generates a one-page executive report from analysis results.
    Translates: "3 god classes" -> "your team loses 8hrs/sprint on 3 over-complex modules"
    """

    def generate(self, results: Dict[str, Any], repo_url: str = "") -> str:
        """Generate complete HTML report ready for browser/PDF.

        Orchestrates the full report pipeline: extracts data from the analysis
        results dictionary, computes financial summaries, and assembles the
        final HTML document from modular section builders.

        Args:
            results: Full analysis results dict from the orchestrator.
            repo_url: The GitHub repository URL that was analyzed.

        Returns:
            A complete, self-contained HTML string suitable for rendering
            in a browser or exporting to PDF.
        """
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        date = datetime.now().strftime("%B %d, %Y")

        detection = results.get("detection", {})
        issues = detection.get("issues", results.get("issues", []))
        hotspots = results.get("hotspots", [])
        silos = results.get("knowledge_silos", [])

        critical = [i for i in issues if i.get("severity") == "CRITICAL"]
        high = [i for i in issues if i.get("severity") == "HIGH"]
        medium = [i for i in issues if i.get("severity") == "MEDIUM"]
        [i for i in issues if i.get("severity") == "LOW"]

        # Financial summary
        debt_data = results.get("debt_interest", {})
        current_cost = debt_data.get(
            "total_current_cost_usd", self._estimate_cost(issues)
        )
        future_cost = debt_data.get("total_future_cost_usd", round(current_cost * 1.23))
        savings = future_cost - current_cost

        # Sprint impact
        sprint_hours = self._sprint_hours(issues)
        sprints_affected = self._sprints_affected(issues)

        # Risk level
        risk = (
            "CRITICAL"
            if critical
            else "HIGH"
            if high
            else "MEDIUM"
            if medium
            else "LOW"
        )
        risk_color = {
            "CRITICAL": "#ef4444",
            "HIGH": "#f97316",
            "MEDIUM": "#f59e0b",
            "LOW": "#22c55e",
        }[risk]

        # Top 3 actions
        actions = self._top_actions(issues, hotspots, silos)

        # Issue type breakdown for business language
        type_summary = self._business_summary(issues)

        # Executive summary text
        exec_summary = self._executive_summary(
            issues, sprint_hours, current_cost, hotspots, silos
        )

        # Assemble HTML from modular sections
        html = '<!DOCTYPE html>\n<html lang="en">\n'
        html += self._build_html_head(repo_name, risk_color)
        html += "<body>\n\n"
        html += self._build_header(repo_name, date, len(issues))
        html += self._build_risk_banner(risk, risk_color, exec_summary)
        html += self._build_metrics_grid(
            len(critical), len(high), sprint_hours, sprints_affected
        )
        html += self._build_cost_section(current_cost, future_cost, savings)
        html += self._build_business_section(type_summary)
        html += self._build_actions_section(actions)
        html += self._hotspot_section(hotspots)
        html += self._silo_section(silos)
        html += self._build_footer(repo_url)
        html += "\n</body>\n</html>"

        return html

    # ── Section Builders ──────────────────────────────────────────────

    def _build_html_head(self, repo_name: str, risk_color: str) -> str:
        """Build the <head> element containing all inline CSS styles.

        Args:
            repo_name: Repository name for the page title.
            risk_color: Hex color string used for risk-related styling.

        Returns:
            Complete <head> HTML string including <style> block.
        """
        return f"""<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Technical Debt Report — {repo_name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f8fafc;
    color: #0f172a;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 2px solid #e2e8f0;
  }}

  .brand {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #64748b;
    margin-bottom: 0.25rem;
  }}

  .repo-name {{
    font-size: 1.75rem;
    font-weight: 800;
    color: #0f172a;
  }}

  .report-meta {{
    text-align: right;
    font-size: 0.8rem;
    color: #64748b;
    line-height: 1.8;
  }}

  .risk-banner {{
    background: {risk_color}18;
    border: 1.5px solid {risk_color}40;
    border-left: 4px solid {risk_color};
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }}

  .risk-label {{
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {risk_color};
    background: {risk_color}20;
    padding: 0.2rem 0.6rem;
    border-radius: 100px;
    white-space: nowrap;
  }}

  .risk-text {{
    font-size: 0.925rem;
    color: #1e293b;
    line-height: 1.5;
  }}

  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
  }}

  .metric-card {{
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.25rem;
    text-align: center;
  }}

  .metric-value {{
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 0.25rem;
  }}

  .metric-label {{
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}

  .section {{
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
  }}

  .section-title {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f1f5f9;
  }}

  .cost-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
  }}

  .cost-card {{
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
  }}

  .cost-card.today {{ background: #eff6ff; border: 1px solid #bfdbfe; }}
  .cost-card.future {{ background: #fff7ed; border: 1px solid #fed7aa; }}
  .cost-card.savings {{ background: #f0fdf4; border: 1px solid #bbf7d0; }}

  .cost-amount {{
    font-size: 1.75rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
  }}

  .cost-card.today .cost-amount {{ color: #2563eb; }}
  .cost-card.future .cost-amount {{ color: #ea580c; }}
  .cost-card.savings .cost-amount {{ color: #16a34a; }}

  .cost-label {{
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  .action-item {{
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    padding: 0.875rem 0;
    border-bottom: 1px solid #f1f5f9;
  }}

  .action-item:last-child {{ border-bottom: none; }}

  .action-num {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #0f172a;
    color: white;
    font-size: 0.8rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 0.1rem;
  }}

  .action-title {{
    font-size: 0.875rem;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 0.2rem;
  }}

  .action-desc {{
    font-size: 0.8rem;
    color: #64748b;
    line-height: 1.5;
  }}

  .summary-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0;
    border-bottom: 1px solid #f1f5f9;
    font-size: 0.875rem;
  }}

  .summary-row:last-child {{ border-bottom: none; }}
  .summary-label {{ color: #475569; }}
  .summary-value {{ font-weight: 600; color: #0f172a; }}

  .hotspot-row {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0;
    border-bottom: 1px solid #f1f5f9;
    font-size: 0.825rem;
  }}

  .hotspot-row:last-child {{ border-bottom: none; }}

  .hs-score {{
    font-weight: 800;
    font-size: 1rem;
    min-width: 36px;
    color: #ef4444;
  }}

  .hs-file {{
    font-family: monospace;
    color: #0f172a;
    flex: 1;
  }}

  .hs-meta {{ color: #94a3b8; font-size: 0.75rem; }}

  .footer {{
    text-align: center;
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #e2e8f0;
  }}
</style>
</head>
"""

    def _build_header(self, repo_name: str, date: str, issue_count: int) -> str:
        """Build the report header with branding and metadata.

        Args:
            repo_name: Repository name to display.
            date: Formatted date string for the report.
            issue_count: Total number of issues detected.

        Returns:
            HTML string for the page header section.
        """
        return f"""<div class="header">
  <div>
    <div class="brand">CodeDebt Guardian — Executive Report</div>
    <div class="repo-name">{repo_name}</div>
  </div>
  <div class="report-meta">
    Generated: {date}<br/>
    Total Issues: {issue_count}<br/>
    Analysis: AI-Powered
  </div>
</div>

"""

    def _build_risk_banner(self, risk: str, risk_color: str, summary_text: str) -> str:
        """Build the risk assessment banner.

        Args:
            risk: Risk level string (CRITICAL, HIGH, MEDIUM, LOW).
            risk_color: Hex color for risk styling.
            summary_text: Executive summary text content.

        Returns:
            HTML string for the risk banner section.
        """
        return f"""<div class="risk-banner">
  <span class="risk-label">{risk} RISK</span>
  <span class="risk-text">
    {summary_text}
  </span>
</div>

"""

    def _build_metrics_grid(
        self, critical_n: int, high_n: int, sprint_hours: int, sprints_affected: int
    ) -> str:
        """Build the 4-card metrics summary grid.

        Args:
            critical_n: Count of critical-severity issues.
            high_n: Count of high-severity issues.
            sprint_hours: Estimated developer hours lost per sprint.
            sprints_affected: Number of sprints impacted.

        Returns:
            HTML string for the metrics grid.
        """
        return f"""<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-value" style="color:#ef4444">{critical_n}</div>
    <div class="metric-label">Critical Issues</div>
  </div>
  <div class="metric-card">
    <div class="metric-value" style="color:#f97316">{high_n}</div>
    <div class="metric-label">High Priority</div>
  </div>
  <div class="metric-card">
    <div class="metric-value" style="color:#0f172a">{sprint_hours}h</div>
    <div class="metric-label">Lost Per Sprint</div>
  </div>
  <div class="metric-card">
    <div class="metric-value" style="color:#0f172a">{sprints_affected}</div>
    <div class="metric-label">Sprints Affected</div>
  </div>
</div>

"""

    def _build_cost_section(
        self, current_cost: float, future_cost: float, savings: float
    ) -> str:
        """Build the financial impact section with cost comparison cards.

        Args:
            current_cost: Current estimated remediation cost in USD.
            future_cost: Projected remediation cost next quarter in USD.
            savings: Potential savings if debt is fixed now in USD.

        Returns:
            HTML string for the financial impact section.
        """
        return f"""<div class="section">
  <div class="section-title">Financial Impact</div>
  <div class="cost-grid">
    <div class="cost-card today">
      <div class="cost-amount">${current_cost:,.0f}</div>
      <div class="cost-label">Fix Cost Today</div>
    </div>
    <div class="cost-card future">
      <div class="cost-amount">${future_cost:,.0f}</div>
      <div class="cost-label">Cost Next Quarter</div>
    </div>
    <div class="cost-card savings">
      <div class="cost-amount">${savings:,.0f}</div>
      <div class="cost-label">Savings If Fixed Now</div>
    </div>
  </div>
</div>

"""

    def _build_business_section(self, type_summary: Dict[str, str]) -> str:
        """Build the business impact summary section.

        Args:
            type_summary: Dict mapping issue descriptions to their business impact.

        Returns:
            HTML string for the business summary section.
        """
        rows = "".join(
            f'<div class="summary-row"><span class="summary-label">{k}</span>'
            f'<span class="summary-value">{v}</span></div>'
            for k, v in type_summary.items()
        )
        return f"""<div class="section">
  <div class="section-title">What This Means For Your Business</div>
  {rows}
</div>

"""

    def _build_actions_section(self, actions: List[Dict]) -> str:
        """Build the top recommended actions section.

        Args:
            actions: List of action dicts with 'title' and 'desc' keys.

        Returns:
            HTML string for the actions section.
        """
        rows = "".join(
            f'<div class="action-item"><div class="action-num">{i + 1}</div>'
            f'<div><div class="action-title">{a["title"]}</div>'
            f'<div class="action-desc">{a["desc"]}</div></div></div>'
            for i, a in enumerate(actions)
        )
        return f"""<div class="section">
  <div class="section-title">Top 3 Recommended Actions</div>
  {rows}
</div>

"""

    def _build_footer(self, repo_url: str) -> str:
        """Build the report footer with attribution.

        Args:
            repo_url: The analyzed repository URL.

        Returns:
            HTML string for the footer.
        """
        return f"""<div class="footer">
  Generated by CodeDebt Guardian · AI-powered technical debt analysis ·
  {repo_url}
</div>
"""

    # ── Data Computation Helpers ──────────────────────────────────────

    def _estimate_cost(self, issues: List[Dict]) -> float:
        """Estimate total remediation cost when debt interest data is unavailable.

        Uses fixed per-severity rates to compute a rough cost estimate.

        Args:
            issues: List of issue dicts, each with a 'severity' key.

        Returns:
            Estimated remediation cost in USD.
        """
        rates = {"CRITICAL": 297, "HIGH": 148, "MEDIUM": 63, "LOW": 25}
        return sum(rates.get(i.get("severity", "LOW"), 25) for i in issues)

    def _sprint_hours(self, issues: List[Dict]) -> int:
        """Calculate total developer hours lost per sprint due to debt.

        Maps each issue severity to an estimated hourly impact and sums
        across all issues.

        Args:
            issues: List of issue dicts, each with a 'severity' key.

        Returns:
            Total hours lost per sprint as an integer.
        """
        hours = {"CRITICAL": 4, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
        return sum(hours.get(i.get("severity", "LOW"), 0) for i in issues)

    def _sprints_affected(self, issues: List[Dict]) -> int:
        """Count the number of distinct sprints affected by debt.

        Uses unique file paths as a proxy for sprint spread — more files
        touched means more sprints disrupted.

        Args:
            issues: List of issue dicts with location information.

        Returns:
            Number of affected sprints (minimum 1).
        """
        files = set(
            i.get("location", {}).get("file_path", "").split(":")[0]
            if isinstance(i.get("location"), dict)
            else str(i.get("location", "")).split(":")[0]
            for i in issues
        )
        return max(len(files), 1)

    def _executive_summary(self, issues, sprint_hours, cost, hotspots, silos) -> str:
        """Generate a one-paragraph executive summary for the risk banner.

        Combines issue count, sprint impact, hotspot count, knowledge silo
        count, and total cost into a concise narrative suitable for
        non-technical executives.

        Args:
            issues: List of all detected issue dicts.
            sprint_hours: Hours lost per sprint.
            cost: Current total remediation cost in USD.
            hotspots: List of hotspot file dicts.
            silos: List of knowledge silo dicts.

        Returns:
            Human-readable summary string, or a default message if no debt.
        """
        parts = []
        if issues:
            parts.append(
                f"Your codebase has {len(issues)} technical debt issues "
                f"costing your team approximately {sprint_hours} hours per sprint."
            )
        if hotspots:
            parts.append(
                f"{len(hotspots)} files are high-risk hotspots — "
                f"complex code that changes frequently."
            )
        if silos:
            parts.append(
                f"{len(silos)} files are known only to one developer (bus factor: 1)."
            )
        if cost:
            parts.append(f"Total remediation cost today: ${cost:,.0f}.")
        return " ".join(parts) if parts else "No significant debt detected."

    def _business_summary(self, issues: List[Dict]) -> Dict[str, str]:
        """Translate raw issue types into business-friendly language.

        Groups issues by type, maps each to a business impact description,
        and returns the top 5 most frequent categories.

        Args:
            issues: List of issue dicts, each with a 'type' key.

        Returns:
            Ordered dict mapping business-friendly labels (with counts)
            to their impact descriptions.
        """
        type_counts = {}
        for i in issues:
            t = i.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        business_lang = {
            "hardcoded_password": (
                "Security credentials in source code",
                "compliance risk, potential breach",
            ),
            "long_method": (
                "Overly complex functions",
                "slow onboarding, high bug risk",
            ),
            "god_class": ("Monolithic modules", "blocks parallel development"),
            "missing_docstring": (
                "Undocumented code",
                "increases onboarding time by 40%",
            ),
            "bare_except": ("Silent error suppression", "bugs hidden until production"),
            "console_log": (
                "Debug code in production",
                "performance and security risk",
            ),
            "callback_hell": ("Deeply nested async code", "high maintenance cost"),
        }

        result = {}
        for itype, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            label, impact = business_lang.get(
                itype, (itype.replace("_", " ").title(), "technical risk")
            )
            result[f"{label} ({count} instances)"] = f"Impact: {impact}"
        return result

    def _top_actions(self, issues, hotspots, silos) -> List[Dict]:
        """Generate the top 3 prioritized remediation actions.

        Examines critical issues, hotspots, and knowledge silos to produce
        concrete, actionable recommendations ordered by urgency.

        Args:
            issues: List of all detected issue dicts.
            hotspots: List of hotspot file dicts.
            silos: List of knowledge silo dicts.

        Returns:
            List of up to 3 action dicts, each with 'title' and 'desc' keys.
        """
        actions = []
        critical = [i for i in issues if i.get("severity") == "CRITICAL"]
        if critical:
            locations = set(
                i.get("location", {}).get("file_path", "").split(":")[0]
                if isinstance(i.get("location"), dict)
                else str(i.get("location", "")).split(":")[0]
                for i in critical
            )
            actions.append(
                {
                    "title": f"Fix {len(critical)} critical security issue(s) immediately",
                    "desc": (
                        f"Hardcoded credentials and critical bugs in "
                        f"{locations}. "
                        f"These are compliance and security risks."
                    ),
                }
            )
        if hotspots:
            h = hotspots[0]
            actions.append(
                {
                    "title": f"Refactor hotspot: {h.get('filepath', '')}",
                    "desc": (
                        f"This file has a hotspot score of {h.get('hotspot_score', 0):.0f} "
                        f"— changed {h.get('commits_90d', 0)}x in 90 days with high complexity. "
                        f"Schedule 1 sprint for refactoring."
                    ),
                }
            )
        if silos:
            s = silos[0]
            actions.append(
                {
                    "title": f"Document knowledge silo: {s.get('filepath', '')}",
                    "desc": (
                        f"Only {s.get('sole_author', '')} understands this file. "
                        f"Schedule pair programming and documentation before this becomes a risk."
                    ),
                }
            )
        high = [i for i in issues if i.get("severity") == "HIGH"]
        if high and len(actions) < 3:
            actions.append(
                {
                    "title": f"Address {len(high)} high-priority issues this quarter",
                    "desc": (
                        "Long methods and complex classes that slow down "
                        "every feature delivery. Allocate 20% of sprint capacity to debt reduction."
                    ),
                }
            )
        return actions[:3]

    def _hotspot_section(self, hotspots: List[Dict]) -> str:
        """Build the code hotspots section showing high-risk files.

        Displays the top 5 files ranked by hotspot score — files that are
        both complex and frequently modified, making them prime refactoring
        targets.

        Args:
            hotspots: List of hotspot dicts with 'hotspot_score', 'filepath',
                     'commits_90d', and 'unique_authors' keys.

        Returns:
            HTML string for the hotspots section, or empty string if none.
        """
        if not hotspots:
            return ""
        rows = ""
        for h in hotspots[:5]:
            rows += (
                '<div class="hotspot-row">'
                + f'<span class="hs-score">{h.get("hotspot_score", 0):.0f}</span>'
                + f'<span class="hs-file">{h.get("filepath", "")}</span>'
                + f'<span class="hs-meta">{h.get("commits_90d", 0)} commits · '
                + f"{h.get('unique_authors', 0)} authors</span></div>"
            )
        return f"""
        <div class="section">
          <div class="section-title">Code Hotspots (Complex + Frequently Changed)</div>
          {rows}
        </div>"""

    def _silo_section(self, silos: List[Dict]) -> str:
        """Build the knowledge silos section highlighting bus-factor risks.

        Shows files that are understood by only one developer, representing
        organizational risk if that person leaves or is unavailable.

        Args:
            silos: List of silo dicts with 'filepath' and 'sole_author' keys.

        Returns:
            HTML string for the silos section, or empty string if none.
        """
        if not silos:
            return ""
        rows = ""
        for s in silos[:3]:
            rows += (
                '<div class="summary-row">'
                + '<span class="summary-label" style="font-family:monospace">'
                + f"{s.get('filepath', '')}</span>"
                + '<span class="summary-value" style="color:#f59e0b">'
                + f"Only: {s.get('sole_author', '')}</span></div>"
            )
        return f"""
        <div class="section">
          <div class="section-title">Knowledge Silos — Bus Factor Risk</div>
          {rows}
        </div>"""

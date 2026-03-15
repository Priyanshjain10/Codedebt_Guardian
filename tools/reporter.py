"""
Report Generator - Formats and presents analysis results.
Supports rich terminal output, JSON, and simple text formats.
"""

import json
import logging
from typing import Any, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
COLORS = {
    "CRITICAL": "\033[91m",  # Red
    "HIGH": "\033[93m",      # Yellow
    "MEDIUM": "\033[94m",    # Blue
    "LOW": "\033[92m",       # Green
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "CYAN": "\033[96m",
    "MAGENTA": "\033[95m",
}

SEVERITY_ICONS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


class ReportGenerator:
    """Generates and renders CodeDebt Guardian analysis reports."""

    def generate(
        self,
        repo_url: str,
        branch: str,
        detection_results: Dict,
        ranked_results: List[Dict],
        fix_proposals: List[Dict],
    ) -> Dict[str, Any]:
        """
        Generate a complete analysis report.

        Returns:
            Structured report dict suitable for JSON export or display
        """
        summary = {
            "total_issues": detection_results.get("total_issues", 0),
            "critical": sum(1 for i in ranked_results if i.get("priority") == "CRITICAL"),
            "high": sum(1 for i in ranked_results if i.get("priority") == "HIGH"),
            "medium": sum(1 for i in ranked_results if i.get("priority") == "MEDIUM"),
            "low": sum(1 for i in ranked_results if i.get("priority") == "LOW"),
            "quick_wins": sum(1 for i in ranked_results if i.get("quick_win", False)),
            "fixes_proposed": len(fix_proposals),
            "files_scanned": detection_results.get("files_scanned", 0),
        }

        # Estimated hours saved (rough heuristic)
        effort_map = {"CRITICAL": 8, "HIGH": 4, "MEDIUM": 2, "LOW": 0.5}
        estimated_hours_saved = sum(
            effort_map.get(i.get("priority", "LOW"), 1) * 0.6  # 60% time saving estimate
            for i in ranked_results
            if i.get("priority") in ["CRITICAL", "HIGH"]
        )
        summary["estimated_hours_saved"] = round(estimated_hours_saved, 1)

        return {
            "meta": {
                "repo_url": repo_url,
                "branch": branch,
                "generated_at": datetime.now().isoformat(),
                "tool": "CodeDebt Guardian v1.0",
            },
            "summary": summary,
            "top_issues": ranked_results[:20],
            "fix_proposals": fix_proposals,
            "repo_metadata": detection_results.get("repo_metadata", {}),
            "stats": detection_results.get("stats", {}),
        }

    def print_summary(self, report: Dict, output_format: str = "rich") -> None:
        """Print report to terminal."""
        if output_format == "json":
            print(json.dumps(report, indent=2, default=str))
            return
        if output_format == "simple":
            self._print_simple(report)
            return
        self._print_rich(report)

    def _print_rich(self, report: Dict) -> None:
        """Print a colorful rich terminal report."""
        summary = report["summary"]
        meta = report["meta"]
        B = COLORS["BOLD"]
        R = COLORS["RESET"]
        C = COLORS["CYAN"]
        M = COLORS["MAGENTA"]
        D = COLORS["DIM"]

        print(f"\n{B}📊 ANALYSIS COMPLETE{R}")
        print(f"{D}Repository: {meta['repo_url']} | Branch: {meta['branch']}{R}")
        print(f"{D}Generated: {meta['generated_at'][:19]}{R}")
        print()

        # Summary box
        print(f"{B}┌─ DEBT SUMMARY {'─' * 42}┐{R}")
        print(f"│  Total Issues Found:    {B}{summary['total_issues']:>4}{R}                           │")
        print(f"│  Files Scanned:         {B}{summary['files_scanned']:>4}{R}                           │")
        print(f"│                                                       │")
        print(f"│  {COLORS['CRITICAL']}🔴 CRITICAL: {summary['critical']:>3}{R}    {COLORS['HIGH']}🟠 HIGH: {summary['high']:>3}{R}                │")
        print(f"│  {COLORS['MEDIUM']}🟡 MEDIUM:   {summary['medium']:>3}{R}    {COLORS['LOW']}🟢 LOW:  {summary['low']:>3}{R}                │")
        print(f"│                                                       │")
        print(f"│  ⚡ Quick Wins:         {B}{summary['quick_wins']:>4}{R}                           │")
        print(f"│  🔧 Fix Proposals:      {B}{summary['fixes_proposed']:>4}{R}                           │")
        print(f"│  ⏱️  Est. Hours Saved:   {B}{summary['estimated_hours_saved']:>4.1f}{R}                           │")
        print(f"{B}└{'─' * 55}┘{R}")

        # Top issues
        top_issues = report.get("top_issues", [])[:10]
        if top_issues:
            print(f"\n{B}🔍 TOP 10 PRIORITY ISSUES{R}")
            print("─" * 60)
            for i, issue in enumerate(top_issues, 1):
                priority = issue.get("priority", "MEDIUM")
                icon = SEVERITY_ICONS.get(priority, "⚪")
                color = COLORS.get(priority, COLORS["RESET"])
                score = issue.get("score", 0)
                location = issue.get("location", "unknown")[:35]
                desc = issue.get("description", "")[:50]
                quick_win = " ⚡" if issue.get("quick_win") else ""
                print(f"  {i:>2}. {color}{icon} [{priority:<8}]{R} Score:{B}{score:>3}{R}{quick_win}")
                print(f"      {D}{location}{R}")
                print(f"      {desc}...")
                print()

        # Fix proposals preview
        fixes = report.get("fix_proposals", [])
        if fixes:
            print(f"{B}🔧 FIX PROPOSALS GENERATED{R}")
            print("─" * 60)
            for fix in fixes[:5]:
                print(f"  ✅ {fix.get('issue_type', 'Unknown')} — {fix.get('fix_summary', '')[:60]}")
            if len(fixes) > 5:
                print(f"  {D}... and {len(fixes) - 5} more. Use --save to get full report.{R}")

        print(f"\n{C}💡 Run with --save to export full JSON report{R}")
        print(f"{C}🌐 Run with --ui to explore in the web interface{R}\n")

    def _print_simple(self, report: Dict) -> None:
        """Print a plain text summary."""
        summary = report["summary"]
        print(f"CodeDebt Guardian Report")
        print(f"Repo: {report['meta']['repo_url']}")
        print(f"Total Issues: {summary['total_issues']}")
        print(f"Critical: {summary['critical']} | High: {summary['high']} | Medium: {summary['medium']} | Low: {summary['low']}")
        print(f"Quick Wins: {summary['quick_wins']}")
        print(f"Fix Proposals: {summary['fixes_proposed']}")
        print(f"Estimated Hours Saved: {summary['estimated_hours_saved']}")

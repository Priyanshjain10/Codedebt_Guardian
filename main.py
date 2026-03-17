"""
CodeDebt Guardian - AI-Powered Technical Debt Detection & Remediation
Main orchestrator that coordinates all agents.
"""

import os
import sys
import argparse
import json
from datetime import datetime

from agents.orchestrator import CodeDebtOrchestrator
from tools.reporter import ReportGenerator


def print_banner():
    banner = """
╔═══════════════════════════════════════════════════════════╗
║          🤖 CodeDebt Guardian v1.0                        ║
║   AI-Powered Technical Debt Detection & Remediation       ║
║   Built with Google ADK + Gemini 2.0                      ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def run_analysis(
    repo_url: str,
    branch: str = "main",
    output_format: str = "rich",
    save_report: bool = False,
    auto_fix: bool = False,
    max_prs: int = 3,
):
    """Run full technical debt analysis on a repository."""
    print_banner()

    # Validate core env — only GITHUB_TOKEN is required for scanning
    if not os.getenv("GITHUB_TOKEN"):
        print("❌ Missing GITHUB_TOKEN environment variable.")
        print("   Set it with: export GITHUB_TOKEN=...")
        sys.exit(1)

    if not os.getenv("GOOGLE_API_KEY"):
        print(
            "⚠️  GOOGLE_API_KEY not set — AI features disabled, running static analysis only"
        )

    print(f"\n🔍 Analyzing repository: {repo_url} (branch: {branch})")
    print("─" * 60)

    orchestrator = CodeDebtOrchestrator()

    # Phase 1: Debt Detection
    print("\n[1/3] 🕵️  Running Debt Detection Agent — downloading & scanning...")
    detection_results = orchestrator.detect_debt(repo_url, branch=branch)
    temp_dir = detection_results.pop("_temp_dir", None)

    try:
        total_issues = detection_results.get("total_issues", 0)
        files_scanned = detection_results.get("files_scanned", 0)
        print(f"      ✅ Scanned {files_scanned} files — found {total_issues} issues")

        # Phase 2: Priority Ranking
        print(
            "\n[2/3] 📊 Running Priority Ranking Agent — scoring by business impact..."
        )
        ranked_results = orchestrator.rank_debt(detection_results)
        critical = sum(1 for i in ranked_results if i.get("priority") == "CRITICAL")
        high = sum(1 for i in ranked_results if i.get("priority") == "HIGH")
        print(
            f"      ✅ Ranked {len(ranked_results)} issues — {critical} CRITICAL, {high} HIGH priority"
        )

        # Phase 3: Fix Proposals
        print("\n[3/3] 🔧 Running Fix Proposal Agent — generating AI fix proposals...")
        fix_proposals = orchestrator.propose_fixes(ranked_results[:10])
        print(f"      ✅ Generated {len(fix_proposals)} actionable fix proposals")

        # ── AUTO-FIX: Create GitHub PRs ─────────────────────────────────
        created_prs = []
        if auto_fix:
            if not os.getenv("GITHUB_TOKEN"):
                print("\n⚠️  --auto-fix requires GITHUB_TOKEN with write access.")
                print("   Skipping PR creation. Scan results are shown below.\n")
            elif not fix_proposals:
                print("\n⚠️  No fix proposals generated — nothing to auto-fix.\n")
            else:
                num_fixes = min(max_prs, len(fix_proposals))
                print(f"\n{'═' * 60}")
                print(
                    f"🤖 AUTO-FIX ENGAGED — Creating {num_fixes} GitHub Pull Request(s)..."
                )
                print(f"{'═' * 60}")

                for i, fix in enumerate(fix_proposals[:num_fixes], 1):
                    issue_type = fix.get("issue_type", fix.get("type", "unknown"))
                    location = fix.get("location", fix.get("file", "unknown"))
                    print(
                        f"\n   [{i}/{num_fixes}] 🔧 Generating AI fix for {issue_type} in {location}..."
                    )

                try:
                    created_prs = orchestrator.create_pull_requests(
                        repo_url=repo_url,
                        fix_proposals=fix_proposals[:num_fixes],
                        ranked_issues=ranked_results,
                        max_prs=num_fixes,
                        base_branch=branch,
                    )

                    if created_prs:
                        print(f"\n   {'─' * 50}")
                        print(
                            f"   🎉 SUCCESS — Created {len(created_prs)} Pull Request(s):\n"
                        )
                        for pr in created_prs:
                            pr_url = pr.get("html_url", pr.get("url", "N/A"))
                            pr_num = pr.get("number", "?")
                            pr_title = pr.get("title", "Fix")[:60]
                            print(f"      [SUCCESS] PR #{pr_num}: {pr_title}")
                            print(f"               🔗 {pr_url}")
                    else:
                        print(
                            "\n   ⚠️  No PRs were created (check repo permissions or file paths)"
                        )
                except Exception as e:
                    print(f"\n   ❌ Auto-fix failed: {e}")
                    print(
                        "      Make sure your GITHUB_TOKEN has write access to the repo"
                    )

        # ── Generate report ─────────────────────────────────────────────
        report_gen = ReportGenerator()
        report = report_gen.generate(
            repo_url=repo_url,
            branch=branch,
            detection_results=detection_results,
            ranked_results=ranked_results,
            fix_proposals=fix_proposals,
        )
        report["pull_requests"] = created_prs

        # Save analysis history
        if hasattr(orchestrator, "memory") and hasattr(
            orchestrator.memory, "save_analysis_history"
        ):
            orchestrator.memory.save_analysis_history(
                repo_url, branch, report.get("summary", {})
            )

        print("\n" + "═" * 60)
        report_gen.print_summary(report, output_format)

        if save_report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"debt_report_{timestamp}.json"
            with open(filename, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n💾 Full report saved to: {filename}")

        return report

    finally:
        # Cleanup temp directory from disk-buffered extraction
        if temp_dir:
            try:
                temp_dir.cleanup()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="🤖 CodeDebt Guardian - AI-Powered Technical Debt Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --repo https://github.com/owner/repo
  python main.py --repo https://github.com/owner/repo --branch develop
  python main.py --repo https://github.com/owner/repo --save --format json
  python main.py --ui   # Launch web interface
        """,
    )

    parser.add_argument("--repo", type=str, help="GitHub repository URL to analyze")
    parser.add_argument(
        "--branch", type=str, default="main", help="Branch to analyze (default: main)"
    )
    parser.add_argument(
        "--format",
        choices=["rich", "json", "simple"],
        default="rich",
        help="Output format",
    )
    parser.add_argument("--save", action="store_true", help="Save report to JSON file")
    parser.add_argument(
        "--ui", action="store_true", help="Launch Streamlit web interface"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="🚀 Autonomously create GitHub PRs with fixes applied",
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=3,
        help="Max PRs to create with --auto-fix (default: 3)",
    )

    args = parser.parse_args()

    if args.ui:
        print("🌐 Launching CodeDebt Guardian Web UI at http://localhost:8000...")
        os.system("python -m http.server 8000 -d ui")
        return

    if not args.repo:
        parser.print_help()
        print("\n💡 Tip: Use --ui to launch the web interface")
        print("💡 Tip: Use --auto-fix to autonomously create GitHub PRs with fixes!")
        sys.exit(0)

    run_analysis(
        repo_url=args.repo,
        branch=args.branch,
        output_format=args.format,
        save_report=args.save,
        auto_fix=args.auto_fix,
        max_prs=args.max_prs,
    )


if __name__ == "__main__":
    main()


# TODO: fix this later
def bad_function(a, b, c, d, e, f, g, h, i, j, k, l_var, m, n, o, p):
    try:
        pass
    except Exception:
        os.environ.get("PASSWORD")
        pass

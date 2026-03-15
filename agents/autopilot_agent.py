
""" AutoPilot Agent — continuously monitors repos and fixes new debt automatically. """
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from tools.change_detector import ChangeDetector
from tools.safety_layer import SafetyLayer
from tools.memory_bank import MemoryBank

logger = logging.getLogger(__name__)

class AutoPilotConfig:
    def __init__(self, max_prs_per_day: int = 3, draft_prs_only: bool = True,
                 allowed_fix_types: Optional[List[str]] = None, dry_run: bool = False):
        self.max_prs_per_day = max_prs_per_day
        self.draft_prs_only = draft_prs_only
        self.allowed_fix_types = allowed_fix_types or ["bare_except", "missing_docstring", "missing_requirements", "no_tests"]
        self.auto_merge = False  # NEVER
        self.dry_run = dry_run

class AutoPilotAgent:
    """Proactive codebase health agent — fixes debt before it accumulates."""

    def __init__(self, config: Optional[AutoPilotConfig] = None):
        self.config = config or AutoPilotConfig()
        self.memory = MemoryBank()
        self.safety = SafetyLayer()
        self.detector = ChangeDetector()
        self._prs_today = 0

    def run(self, repo_url: str) -> Dict[str, Any]:
        start = datetime.now()
        owner, repo = repo_url.rstrip("/").split("/")[-2:]
        logger.info(f"AutoPilot starting: {owner}/{repo}")

        result = {"repo_url": repo_url, "started_at": start.isoformat(),
                  "files_analyzed": 0, "issues_found": 0, "prs_created": [], 
                  "prs_skipped": [], "errors": [], "dry_run": self.config.dry_run}

        if self._prs_today >= self.config.max_prs_per_day:
            result["errors"].append("Daily PR limit reached")
            return result

        changed_files = self.detector.get_changed_files(owner, repo)
        result["files_analyzed"] = len(changed_files)

        if not changed_files:
            return result

        from agents.debt_detection_agent import DebtDetectionAgent
        from agents.fix_proposal_agent import FixProposalAgent

        detect = DebtDetectionAgent(memory=self.memory)
        fix_agent = FixProposalAgent(memory=self.memory)

        for file_info in changed_files:
            issues = detect._run_static_analysis(file_info)
            safe = [i for i in issues if i.get("type") in self.config.allowed_fix_types]
            result["issues_found"] += len(safe)

            for issue in safe:
                if self._prs_today >= self.config.max_prs_per_day:
                    break
                template = fix_agent._fix_templates.get(issue.get("type", ""))
                if not template:
                    result["prs_skipped"].append({"type": issue.get("type"), "reason": "No template"})
                    continue
                fix = fix_agent._apply_template(issue, template)
                if not fix:
                    result["prs_skipped"].append({"type": issue.get("type"), "reason": "Template failed"})
                    continue

                if fix.get("before_code") and fix.get("after_code"):
                    ok, reason = self.safety.validate(fix["before_code"], fix["after_code"])
                    if not ok:
                        result["prs_skipped"].append({"type": issue.get("type"), "reason": reason})
                        continue

                if self.config.dry_run:
                    result["prs_created"].append({"type": issue.get("type"), "dry_run": True})
                    logger.info(f"DRY RUN: Would fix {issue.get('type')} in {file_info['name']}")
                else:
                    try:
                        from tools.pr_generator import PRGenerator
                        pr_gen = PRGenerator()
                        pr = pr_gen.create_fix_pr(
                            repo_url=repo_url,
                            issue=issue,
                            fix_proposal=fix,
                        )
                        self._prs_today += 1
                        result["prs_created"].append({
                            "type": issue.get("type"),
                            "file": file_info["name"],
                            "pr_url": pr.get("html_url") if pr else None,
                            "pr_number": pr.get("number") if pr else None,
                        })
                    except Exception as e:
                        result["errors"].append(f"PR creation failed: {str(e)}")

        result["duration_seconds"] = round((datetime.now() - start).total_seconds(), 2)
        result["safety_stats"] = self.safety.stats()
        logger.info(f"AutoPilot done: {result['issues_found']} issues, {len(result['prs_created'])} PRs")
        return result

    def generate_report(self, results: List[Dict]) -> str:
        total_prs = sum(len(r.get("prs_created", [])) for r in results)
        total_issues = sum(r.get("issues_found", 0) for r in results)
        return f"""
╔══════════════════════════════════════════╗
║   🤖 CodeDebt Guardian AutoPilot Report  ║
║   {datetime.now().strftime("%Y-%m-%d")}                          ║
╚══════════════════════════════════════════╝
  Issues Found:  {total_issues}
  PRs Created:   {total_prs} (draft only, review before merging)
  Safety:        All fixes validated before PR creation
"""

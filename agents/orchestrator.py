"""
Orchestrator Agent - Coordinates the multi-agent pipeline.
Manages session state, memory, and agent communication.
"""

import json
import hashlib
import logging
import tempfile
import shutil
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from agents.debt_detection_agent import DebtDetectionAgent, QuotaExhaustedError
from agents.priority_ranking_agent import PriorityRankingAgent
from agents.fix_proposal_agent import FixProposalAgent
from tools.persistent_memory import PersistentMemoryBank
from tools.memory_bank import MemoryBank
from tools.observability import ObservabilityLayer
from tools.pr_generator import PRGenerator

logger = logging.getLogger(__name__)

try:
    from tools.tdr_calculator import TDRCalculator

    _tdr_calculator = TDRCalculator()
    TDR_SUPPORT = True
except Exception:
    TDR_SUPPORT = False

try:
    from tools.hotspot_analyzer import HotspotAnalyzer

    _hotspot_analyzer = HotspotAnalyzer()
    HOTSPOT_SUPPORT = True
except Exception:
    HOTSPOT_SUPPORT = False


class SessionState:
    """Manages conversation and analysis state across agent calls."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.history: List[Dict] = []
        self.metadata: Dict[str, Any] = {}

    def add_event(self, agent: str, event_type: str, data: Any):
        self.history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent": agent,
                "event": event_type,
                "data": data,
            }
        )

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "history": self.history,
            "metadata": self.metadata,
        }


class CodeDebtOrchestrator:
    """
    Master orchestrator that coordinates the three specialized agents:
    1. DebtDetectionAgent - scans code for technical debt
    2. PriorityRankingAgent - scores and ranks issues by business impact
    3. FixProposalAgent - generates actionable fix suggestions

    Uses sequential agent coordination with shared memory and observability.
    """

    def __init__(self, use_persistent_memory: bool = True):
        # Use SQLite-backed memory if available, else fallback to in-memory
        try:
            self.memory = (
                PersistentMemoryBank() if use_persistent_memory else MemoryBank()
            )
        except Exception:
            logger.warning("PersistentMemoryBank failed, falling back to in-memory")
            self.memory = MemoryBank()

        self.obs = ObservabilityLayer(service_name="orchestrator")

        # Initialize all specialized agents
        self.detection_agent = DebtDetectionAgent(memory=self.memory)
        self.ranking_agent = PriorityRankingAgent(memory=self.memory)
        self.fix_agent = FixProposalAgent(memory=self.memory)

        # PR generator (lazy-initialized when needed)
        self._pr_generator: PRGenerator = None

        # Session management
        self._sessions: Dict[str, SessionState] = {}

        logger.info("CodeDebt Orchestrator initialized with 3 agents")

    def _get_or_create_session(self, repo_url: str) -> SessionState:
        """Get existing or create new session for a repo."""
        session_id = f"session_{hashlib.sha256(repo_url.encode()).hexdigest()[:16]}"
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id)
            logger.info(f"Created new session: {session_id}")
        return self._sessions[session_id]

    def detect_debt(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Phase 1: Run the Debt Detection Agent.
        Scans the repository for technical debt patterns.
        """
        session = self._get_or_create_session(repo_url)

        with self.obs.trace("detect_debt") as span:
            span.set_attribute("repo_url", repo_url)
            span.set_attribute("branch", branch)

            # Check memory for cached results
            cache_key = f"detection_{repo_url}_{branch}"
            cached = self.memory.get(cache_key)
            if cached:
                logger.info(f"Cache hit for detection: {cache_key}")
                span.set_attribute("cache_hit", True)
                session.add_event("orchestrator", "cache_hit", {"key": cache_key})
                return cached

            # Run detection agent
            results = self.detection_agent.analyze(repo_url=repo_url, branch=branch)

            # Store in memory bank
            self.memory.set(cache_key, results, ttl_seconds=3600)
            session.add_event(
                "detection_agent",
                "completed",
                {
                    "total_issues": results.get("total_issues", 0),
                    "files_scanned": results.get("files_scanned", 0),
                },
            )

            span.set_attribute("issues_found", results.get("total_issues", 0))
            return results

    def rank_debt(self, detection_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Phase 2: Run the Priority Ranking Agent.
        Scores each debt item by impact, effort, and risk.
        """
        with self.obs.trace("rank_debt") as span:
            issues = detection_results.get("issues", [])
            span.set_attribute("input_issues", len(issues))

            ranked = self.ranking_agent.rank(
                issues=issues, repo_metadata=detection_results.get("repo_metadata", {})
            )

            span.set_attribute("ranked_issues", len(ranked))
            return ranked

    def propose_fixes(
        self, ranked_issues: List[Dict[str, Any]], project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Phase 3: Run the Fix Proposal Agent.
        Generates concrete fix suggestions for top priority issues.
        """
        with self.obs.trace("propose_fixes") as span:
            span.set_attribute("issues_to_fix", len(ranked_issues))

            proposals = self.fix_agent.propose(
                issues=ranked_issues, project_id=project_id
            )

            span.set_attribute("proposals_generated", len(proposals))
            return proposals

    def run_full_analysis(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Run the complete multi-agent pipeline end-to-end.
        Returns a comprehensive analysis report.
        """
        start = datetime.now()
        logger.info(f"Starting full analysis: {repo_url}")

        detection_results = self.detect_debt(repo_url, branch)
        temp_dir = detection_results.pop("_temp_dir", None)

        try:
            ranked_results = self.rank_debt(detection_results)
            fix_proposals = self.propose_fixes(ranked_results[:10])

            duration = (datetime.now() - start).total_seconds()

            # Hotspot + knowledge silo analysis
            hotspots = []
            silos = []
            if HOTSPOT_SUPPORT:
                try:
                    parts = repo_url.rstrip("/").split("/")
                    _, _ = parts[-2], parts[-1].replace(".git", "")
                    hotspots = _hotspot_analyzer.analyze(
                        detection_results.get("issues", [])
                    )
                    logger.info(f"Hotspots: {len(hotspots)}, Silos: {len(silos)}")
                except Exception as e:
                    logger.warning(f"Hotspot analysis failed: {e}")

            return {
                "repo_url": repo_url,
                "branch": branch,
                "analyzed_at": start.isoformat(),
                "duration_seconds": round(duration, 2),
                "detection": detection_results,
                "ranked_issues": ranked_results,
                "hotspots": hotspots,
                "tdr": self._safe_tdr_calculate(detection_results),
                "knowledge_silos": silos,
                "fix_proposals": fix_proposals,
                "summary": {
                    "total_issues": detection_results.get("total_issues", 0),
                    "critical": sum(
                        1 for i in ranked_results if i.get("priority") == "CRITICAL"
                    ),
                    "high": sum(
                        1 for i in ranked_results if i.get("priority") == "HIGH"
                    ),
                    "medium": sum(
                        1 for i in ranked_results if i.get("priority") == "MEDIUM"
                    ),
                    "low": sum(1 for i in ranked_results if i.get("priority") == "LOW"),
                    "fixes_proposed": len(fix_proposals),
                },
            }
        finally:
            # Cleanup: delete temp directory to prevent disk leak
            if temp_dir:
                try:
                    if hasattr(temp_dir, "cleanup"):
                        temp_dir.cleanup()
                    else:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info("Cleaned up temporary extraction directory")
                except Exception as e:
                    logger.warning(f"Temp dir cleanup failed: {e}")

    def run_full_analysis_stream(self, repo_url: str, branch: str = "main"):
        """
        Streaming version of run_full_analysis.
        Yields newline-delimited JSON events for real-time progress reporting.

        Event format:
            {"status": "progress", "message": "..."} — intermediate update
            {"status": "complete", "data": {...}}     — final result payload
            {"status": "error", "message": "..."}     — fatal error
        """
        start = datetime.now()
        logger.info(f"Starting streaming analysis: {repo_url}")

        yield (
            json.dumps(
                {
                    "status": "progress",
                    "message": "[SYS] Initializing CodeDebt Guardian pipeline...",
                }
            )
            + "\n"
        )

        temp_dir = None  # Initialize temp_dir outside try block

        try:
            # Phase 1: Debt Detection
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": "[1/4] \U0001f575\ufe0f  Running Debt Detection Agent — downloading ZIP archive...",
                    }
                )
                + "\n"
            )
            quota_hit = False
            try:
                detection_results = self.detect_debt(repo_url, branch)
            except QuotaExhaustedError as e:
                yield (
                    json.dumps(
                        {
                            "status": "quota_exceeded",
                            "message": str(e),
                            "resets_in": "24h",
                        }
                    )
                    + "\n"
                )
                quota_hit = True
                # Re-run detection with AI disabled by clearing the model
                self.detection_agent.model = None
                detection_results = self.detect_debt(repo_url, branch)
            temp_dir = detection_results.pop("_temp_dir", None)
            total_issues = detection_results.get("total_issues", 0)
            files_scanned = detection_results.get("files_scanned", 0)

            # SATD observability — count SATD-specific issues for stream reporting
            satd_count = sum(
                1
                for i in detection_results.get("issues", [])
                if i.get("source") == "satd_analysis"
            )
            satd_msg = (
                f" ({satd_count} SATD comments classified by Gemini)"
                if satd_count
                else ""
            )
            quota_note = (
                " (AI quota reached — static results only)" if quota_hit else ""
            )
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": f"[1/4] \u2705 Scanned {files_scanned} files — found {total_issues} issues{satd_msg}{quota_note}",
                    }
                )
                + "\n"
            )

            # Phase 2: Priority Ranking
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": "[2/4] \U0001f4ca Running Priority Ranking Agent — scoring by business impact...",
                    }
                )
                + "\n"
            )
            ranked_results = self.rank_debt(detection_results)
            critical = sum(1 for i in ranked_results if i.get("priority") == "CRITICAL")
            high = sum(1 for i in ranked_results if i.get("priority") == "HIGH")
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": f"[2/4] \u2705 Ranked {len(ranked_results)} issues — {critical} CRITICAL, {high} HIGH priority",
                    }
                )
                + "\n"
            )

            # Phase 3: Fix Proposals
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": "[3/4] \U0001f527 Generating AI fix proposals for top 10 issues...",
                    }
                )
                + "\n"
            )
            fix_proposals = self.propose_fixes(ranked_results[:10])
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": f"[3/4] \u2705 Generated {len(fix_proposals)} actionable fix proposals",
                    }
                )
                + "\n"
            )

            # Phase 4: Hotspot + TDR
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": "[4/4] \U0001f525 Computing TDR health score & hotspot analysis...",
                    }
                )
                + "\n"
            )
            hotspots = []
            silos = []
            if HOTSPOT_SUPPORT:
                try:
                    parts = repo_url.rstrip("/").split("/")
                    _, _ = parts[-2], parts[-1].replace(".git", "")
                    hotspots = _hotspot_analyzer.analyze(
                        detection_results.get("issues", [])
                    )
                except Exception as e:
                    logger.warning(f"Hotspot analysis failed: {e}")

            tdr = (
                _tdr_calculator.calculate(
                    issues=detection_results.get("issues", []),
                    files_scanned=detection_results.get("files_scanned", 0),
                )
                if TDR_SUPPORT
                else {}
            )

            duration = (datetime.now() - start).total_seconds()
            grade = tdr.get("grade", "N/A")
            yield (
                json.dumps(
                    {
                        "status": "progress",
                        "message": f"[4/4] \u2705 Health grade: {grade} — analysis completed in {duration:.1f}s",
                    }
                )
                + "\n"
            )

            # Final payload
            scan_id = hashlib.md5(repo_url.encode()).hexdigest()[:12]
            final_result = {
                "repo_url": repo_url,
                "branch": branch,
                "analyzed_at": start.isoformat(),
                "duration_seconds": round(duration, 2),
                "detection": detection_results,
                "ranked_issues": ranked_results,
                "hotspots": hotspots,
                "tdr": tdr,
                "knowledge_silos": silos,
                "fix_proposals": fix_proposals,
                "summary": {
                    "total_issues": total_issues,
                    "critical": critical,
                    "high": high,
                    "medium": sum(
                        1 for i in ranked_results if i.get("priority") == "MEDIUM"
                    ),
                    "low": sum(1 for i in ranked_results if i.get("priority") == "LOW"),
                    "fixes_proposed": len(fix_proposals),
                },
            }

            # Save to disk cache for CTO report generation
            self._save_scan_cache(scan_id, final_result)

            yield (
                json.dumps(
                    {"status": "complete", "data": final_result, "scan_id": scan_id},
                    default=str,
                )
                + "\n"
            )

        except Exception as e:
            logger.error(f"Streaming analysis failed: {e}", exc_info=True)
            yield (
                json.dumps({"status": "error", "message": f"[FATAL ERROR] {str(e)}"})
                + "\n"
            )
        finally:
            # Cleanup: delete temp directory to prevent disk leak
            if temp_dir:
                try:
                    temp_dir.cleanup()
                    logger.info("Cleaned up temporary extraction directory")
                except Exception as e:
                    logger.warning(f"Temp dir cleanup failed: {e}")

    def get_session_history(self, repo_url: str) -> Dict:
        """Get full session history for a repository analysis."""
        session = self._get_or_create_session(repo_url)
        return session.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Get observability metrics from all agents."""
        return {
            "orchestrator": self.obs.get_metrics(),
            "detection_agent": self.detection_agent.obs.get_metrics(),
            "ranking_agent": self.ranking_agent.obs.get_metrics(),
            "fix_agent": self.fix_agent.obs.get_metrics(),
            "memory_stats": self.memory.stats(),
            "token_usage": {
                "input": (
                    self.detection_agent.token_usage.get("input", 0)
                    + self.ranking_agent.token_usage.get("input", 0)
                    + self.fix_agent.token_usage.get("input", 0)
                ),
                "output": (
                    self.detection_agent.token_usage.get("output", 0)
                    + self.ranking_agent.token_usage.get("output", 0)
                    + self.fix_agent.token_usage.get("output", 0)
                ),
                "model_usage": {
                    "groq": (
                        self.detection_agent.token_usage.get("model_usage", {}).get(
                            "groq", 0
                        )
                        + self.ranking_agent.token_usage.get("model_usage", {}).get(
                            "groq", 0
                        )
                        + self.fix_agent.token_usage.get("model_usage", {}).get(
                            "groq", 0
                        )
                    ),
                    "gemini": (
                        self.detection_agent.token_usage.get("model_usage", {}).get(
                            "gemini", 0
                        )
                        + self.ranking_agent.token_usage.get("model_usage", {}).get(
                            "gemini", 0
                        )
                        + self.fix_agent.token_usage.get("model_usage", {}).get(
                            "gemini", 0
                        )
                    ),
                },
            },
        }

    def _safe_tdr_calculate(self, detection_results: Dict) -> Dict:
        """Guard TDR calculation against temp dir cleanup failures."""
        if not TDR_SUPPORT:
            return {}
        try:
            return _tdr_calculator.calculate(
                issues=detection_results.get("issues", []),
                files_scanned=detection_results.get("files_scanned", 0),
            )
        except Exception as e:
            logger.warning(f"TDR calculation failed (temp dir may be cleaned up): {e}")
            return {}

    def create_pull_requests(
        self,
        repo_url: str,
        fix_proposals: List[Dict],
        ranked_issues: List[Dict],
        max_prs: int = 3,
        base_branch: str = "main",
    ) -> List[Dict]:
        """
        Autonomously create GitHub Pull Requests with fixes applied.
        This is the key differentiator — not just detecting debt, but FIXING it.

        Args:
            repo_url: GitHub repository URL
            fix_proposals: Fix proposals from FixProposalAgent
            ranked_issues: Ranked issues from PriorityRankingAgent
            max_prs: Maximum number of PRs to create
            base_branch: Branch to base PRs on

        Returns:
            List of created PR info dicts with URLs
        """
        if not self._pr_generator:
            self._pr_generator = PRGenerator()

        with self.obs.trace("create_pull_requests") as span:
            span.set_attribute("max_prs", max_prs)
            prs = self._pr_generator.create_batch_prs(
                repo_url=repo_url,
                fix_proposals=fix_proposals,
                ranked_issues=ranked_issues,
                max_prs=max_prs,
                base_branch=base_branch,
            )
            span.set_attribute("prs_created", len(prs))
            logger.info(f"Created {len(prs)} pull requests")
            return prs

    def get_analysis_history(self, repo_url: str) -> List[Dict]:
        """Get historical analysis results for a repository."""
        if hasattr(self.memory, "get_analysis_history"):
            return self.memory.get_analysis_history(repo_url)
        return []

    # ── Disk cache for CTO reports ───────────────────────────────────────

    _CACHE_DIR = Path(tempfile.gettempdir()) / "scans"

    def _save_scan_cache(self, scan_id: str, data: Dict) -> None:
        """Save analysis results to disk so the /report endpoint can read later."""
        try:
            self._CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = self._CACHE_DIR / f"{scan_id}.json"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str)
            logger.info(f"Scan results cached to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache scan results: {e}")

    @staticmethod
    def load_scan_cache(scan_id: str) -> Optional[Dict]:
        """Load cached analysis results by scan_id. Returns None if not found."""
        cache_path = CodeDebtOrchestrator._CACHE_DIR / f"{scan_id}.json"
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load scan cache {scan_id}: {e}")
            return None

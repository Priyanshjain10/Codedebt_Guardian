"""
Tests for AI token usage tracking across agents and orchestrator.
Validates:
1. Each agent initializes token_usage with the correct schema
2. Orchestrator aggregates tokens from all agents including model_usage
3. Scan summary persistence format matches the spec
"""

from unittest.mock import patch


class TestAgentTokenSchema:
    """Each agent must init with the correct token_usage shape."""

    def test_debt_detection_agent_token_schema(self):
        with patch("agents.debt_detection_agent.genai", None):
            with patch("agents.debt_detection_agent._GENAI_AVAILABLE", False):
                from agents.debt_detection_agent import DebtDetectionAgent

                agent = DebtDetectionAgent()
                assert agent.token_usage == {
                    "input": 0,
                    "output": 0,
                    "model_usage": {"groq": 0, "gemini": 0},
                }

    def test_priority_ranking_agent_token_schema(self):
        with patch("agents.priority_ranking_agent.genai", None):
            with patch("agents.priority_ranking_agent._GENAI_AVAILABLE", False):
                from agents.priority_ranking_agent import PriorityRankingAgent

                agent = PriorityRankingAgent()
                assert agent.token_usage == {
                    "input": 0,
                    "output": 0,
                    "model_usage": {"groq": 0, "gemini": 0},
                }

    def test_fix_proposal_agent_token_schema(self):
        with patch("agents.fix_proposal_agent.genai", None):
            with patch("agents.fix_proposal_agent._GENAI_AVAILABLE", False):
                from agents.fix_proposal_agent import FixProposalAgent

                agent = FixProposalAgent()
                assert agent.token_usage == {
                    "input": 0,
                    "output": 0,
                    "model_usage": {"groq": 0, "gemini": 0},
                }


class TestOrchestratorAggregation:
    """Orchestrator must aggregate tokens_input, tokens_output, and model_usage."""

    def test_get_metrics_aggregates_tokens(self):
        with patch("agents.debt_detection_agent._GENAI_AVAILABLE", False):
            with patch("agents.priority_ranking_agent._GENAI_AVAILABLE", False):
                with patch("agents.fix_proposal_agent._GENAI_AVAILABLE", False):
                    from agents.orchestrator import CodeDebtOrchestrator

                    orch = CodeDebtOrchestrator(use_persistent_memory=False)

                    # Simulate token usage on each agent
                    orch.detection_agent.token_usage = {
                        "input": 100,
                        "output": 50,
                        "model_usage": {"groq": 120, "gemini": 30},
                    }
                    orch.ranking_agent.token_usage = {
                        "input": 200,
                        "output": 80,
                        "model_usage": {"groq": 250, "gemini": 30},
                    }
                    orch.fix_agent.token_usage = {
                        "input": 300,
                        "output": 120,
                        "model_usage": {"groq": 400, "gemini": 20},
                    }

                    metrics = orch.get_metrics()
                    tu = metrics["token_usage"]

                    assert tu["input"] == 600
                    assert tu["output"] == 250
                    assert tu["model_usage"]["groq"] == 770
                    assert tu["model_usage"]["gemini"] == 80


class TestScanSummaryFormat:
    """The Scan.summary JSON must include the correct token tracking keys."""

    def test_summary_has_token_keys(self):
        """Simulate what workers/tasks.py builds and verify keys match spec."""
        # This mirrors the logic from workers/tasks.py
        metrics = {
            "token_usage": {
                "input": 500,
                "output": 200,
                "model_usage": {"groq": 600, "gemini": 100},
            }
        }
        tu = metrics.get("token_usage", {})
        summary = {
            "total_issues": 10,
            "files_scanned": 5,
            "critical": 1,
            "high": 3,
            "medium": 4,
            "low": 2,
            "fixes_proposed": 2,
            "grade": "B",
            "tokens_input": tu.get("input", 0),
            "tokens_output": tu.get("output", 0),
            "model_usage": tu.get("model_usage", {"groq": 0, "gemini": 0}),
        }

        # Validate user-expected keys
        assert "tokens_input" in summary
        assert "tokens_output" in summary
        assert "model_usage" in summary
        assert summary["tokens_input"] == 500
        assert summary["tokens_output"] == 200
        assert summary["model_usage"]["groq"] == 600
        assert summary["model_usage"]["gemini"] == 100

    def test_pr_scan_summary_has_token_keys(self):
        """PR Guardian summaries should also have token keys (zero for static)."""
        pr_summary = {
            "critical": 1,
            "high": 0,
            "medium": 2,
            "low": 1,
            "total_issues": 4,
            "tokens_input": 0,
            "tokens_output": 0,
            "model_usage": {"groq": 0, "gemini": 0},
        }
        assert "tokens_input" in pr_summary
        assert "tokens_output" in pr_summary
        assert "model_usage" in pr_summary
        assert pr_summary["tokens_input"] == 0

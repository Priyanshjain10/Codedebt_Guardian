"""
Test Suite for CodeDebt Guardian
Tests all agents, tools, and core logic.
"""

import pytest
import ast
from unittest.mock import MagicMock, patch

# ─── Tools Tests ──────────────────────────────────────────────────────────────

class TestMemoryBank:
    def setup_method(self):
        from tools.memory_bank import MemoryBank
        self.memory = MemoryBank()

    def test_set_and_get(self):
        self.memory.set("key1", {"data": "value"})
        result = self.memory.get("key1")
        assert result == {"data": "value"}

    def test_get_missing_key_returns_none(self):
        result = self.memory.get("nonexistent")
        assert result is None

    def test_ttl_expiry(self):
        import time
        self.memory.set("expiring", "data", ttl_seconds=1)
        assert self.memory.get("expiring") == "data"
        time.sleep(1.1)
        assert self.memory.get("expiring") is None

    def test_delete(self):
        self.memory.set("to_delete", "value")
        self.memory.delete("to_delete")
        assert self.memory.get("to_delete") is None

    def test_stats_hit_rate(self):
        self.memory.set("k", "v")
        self.memory.get("k")     # hit
        self.memory.get("miss")  # miss
        stats = self.memory.stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == 50.0


class TestObservabilityLayer:
    def setup_method(self):
        from tools.observability import ObservabilityLayer
        self.obs = ObservabilityLayer(service_name="test_service")

    def test_span_records_duration(self):
        import time
        with self.obs.trace("test_op") as span:
            span.set_attribute("key", "value")
            time.sleep(0.01)
        metrics = self.obs.get_metrics()
        assert "test_op" in metrics["operations"]
        assert metrics["operations"]["test_op"]["count"] == 1
        assert metrics["operations"]["test_op"]["avg_ms"] > 0

    def test_error_tracking(self):
        with pytest.raises(ValueError):
            with self.obs.trace("failing_op"):
                raise ValueError("Test error")
        metrics = self.obs.get_metrics()
        assert metrics["error_count"] == 1

    def test_multiple_spans(self):
        for _ in range(3):
            with self.obs.trace("repeated_op"):
                pass
        metrics = self.obs.get_metrics()
        assert metrics["operations"]["repeated_op"]["count"] == 3


class TestCodeAnalyzer:
    def setup_method(self):
        from tools.code_analyzer import CodeAnalyzer
        self.analyzer = CodeAnalyzer()

    def test_basic_metrics(self):
        code = '''
def hello(name):
    """Say hello."""
    return f"Hello, {name}"

class Greeter:
    """A greeter class."""
    def greet(self, name):
        return hello(name)
'''
        metrics = self.analyzer.compute_metrics(code, "test.py")
        assert metrics["lines_of_code"] > 0
        assert len(metrics["functions"]) == 2
        assert len(metrics["classes"]) == 1

    def test_syntax_error_handling(self):
        bad_code = "def broken(:"
        metrics = self.analyzer.compute_metrics(bad_code, "bad.py")
        assert metrics["parse_error"] is not None

    def test_detects_type_hints(self):
        code = "def greet(name: str) -> str:\n    return name"
        metrics = self.analyzer.compute_metrics(code)
        assert metrics["has_type_hints"] is True

    def test_no_type_hints(self):
        code = "def greet(name):\n    return name"
        metrics = self.analyzer.compute_metrics(code)
        assert metrics["has_type_hints"] is False

    def test_cyclomatic_complexity(self):
        simple = "def f():\n    return 1"
        complex_code = """
def f(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x
    elif x < 0:
        return -x
    return 0
"""
        simple_metrics = self.analyzer.compute_metrics(simple)
        complex_metrics = self.analyzer.compute_metrics(complex_code)
        assert complex_metrics["cyclomatic_complexity"] > simple_metrics["cyclomatic_complexity"]


class TestGitHubTool:
    def setup_method(self):
        from tools.github_tool import GitHubTool
        self.github = GitHubTool()

    def test_parse_repo_url_https(self):
        owner, repo = self.github.parse_repo_url("https://github.com/psf/requests")
        assert owner == "psf"
        assert repo == "requests"

    def test_parse_repo_url_shorthand(self):
        owner, repo = self.github.parse_repo_url("psf/requests")
        assert owner == "psf"
        assert repo == "requests"

    def test_parse_repo_url_with_git(self):
        owner, repo = self.github.parse_repo_url("https://github.com/psf/requests.git")
        assert owner == "psf"
        assert repo == "requests"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            self.github.parse_repo_url("not-a-url")


# ─── Agent Tests ──────────────────────────────────────────────────────────────

class TestDebtDetectionAgent:
    def setup_method(self):
        from agents.debt_detection_agent import DebtDetectionAgent
        from tools.memory_bank import MemoryBank
        self.agent = DebtDetectionAgent(memory=MemoryBank())

    def test_detects_long_function(self):
        """Test that functions over 50 lines are flagged."""
        lines = ["    pass\n"] * 60
        code = "def huge_function():\n" + "".join(lines)
        file_info = {"name": "test.py", "content": code}
        issues = self.agent._run_static_analysis(file_info)
        types = [i["type"] for i in issues]
        assert "long_method" in types

    def test_detects_bare_except(self):
        """Test that bare except clauses are detected."""
        code = """
try:
    x = 1 / 0
except:
    pass
"""
        file_info = {"name": "test.py", "content": code}
        issues = self.agent._run_static_analysis(file_info)
        types = [i["type"] for i in issues]
        assert "bare_except" in types

    def test_detects_hardcoded_password(self):
        """Test that hardcoded passwords are flagged."""
        code = 'password = "super_secret_123"\n'
        file_info = {"name": "config.py", "content": code}
        issues = self.agent._run_static_analysis(file_info)
        types = [i["type"] for i in issues]
        assert "hardcoded_password" in types

    def test_detects_missing_docstring(self):
        """Test that functions without docstrings are flagged (if long enough)."""
        lines = "    x = x + 1\n" * 15
        code = f"def no_docs(x):\n{lines}    return x"
        file_info = {"name": "test.py", "content": code}
        issues = self.agent._run_static_analysis(file_info)
        types = [i["type"] for i in issues]
        assert "missing_docstring" in types

    def test_syntax_error_flagged(self):
        """Test that syntax errors are properly caught and reported."""
        code = "def broken(:\n    pass"
        file_info = {"name": "bad.py", "content": code}
        issues = self.agent._run_static_analysis(file_info)
        assert any(i["type"] == "syntax_error" for i in issues)

    def test_deduplicate(self):
        """Test that duplicate issues are removed."""
        issues = [
            {"type": "bare_except", "location": "test.py:5"},
            {"type": "bare_except", "location": "test.py:5"},  # duplicate
            {"type": "long_method", "location": "test.py:10"},
        ]
        unique = self.agent._deduplicate(issues)
        assert len(unique) == 2

    def test_compute_stats(self):
        """Test statistics computation."""
        issues = [
            {"severity": "CRITICAL", "type": "hardcoded_password", "source": "static_analysis"},
            {"severity": "HIGH", "type": "long_method", "source": "static_analysis"},
            {"severity": "MEDIUM", "type": "bare_except", "source": "gemini_ai"},
        ]
        stats = self.agent._compute_stats(issues)
        assert stats["by_severity"]["CRITICAL"] == 1
        assert stats["by_severity"]["HIGH"] == 1
        assert stats["by_type"]["long_method"] == 1


class TestPriorityRankingAgent:
    def setup_method(self):
        from agents.priority_ranking_agent import PriorityRankingAgent
        from tools.memory_bank import MemoryBank
        self.agent = PriorityRankingAgent(memory=MemoryBank())

    def test_critical_ranked_higher_than_low(self):
        """Critical issues should have higher scores than low issues."""
        critical = self.agent._score_issue({"severity": "CRITICAL", "type": "hardcoded_password", "effort_to_fix": "MINUTES"}, 0)
        low = self.agent._score_issue({"severity": "LOW", "type": "missing_docstring", "effort_to_fix": "MINUTES"}, 1)
        assert critical["score"] > low["score"]

    def test_quick_win_flagged_correctly(self):
        """MINUTES effort + high score should be flagged as quick win."""
        issue = self.agent._score_issue({"severity": "CRITICAL", "type": "bare_except", "effort_to_fix": "MINUTES"}, 0)
        assert issue["quick_win"] is True

    def test_days_effort_not_quick_win(self):
        """DAYS effort should not be a quick win."""
        issue = self.agent._score_issue({"severity": "HIGH", "type": "god_class", "effort_to_fix": "DAYS"}, 0)
        assert issue["quick_win"] is False

    def test_score_to_priority_critical(self):
        assert self.agent._score_to_priority(90) == "CRITICAL"

    def test_score_to_priority_high(self):
        assert self.agent._score_to_priority(60) == "HIGH"

    def test_score_to_priority_low(self):
        assert self.agent._score_to_priority(10) == "LOW"

    def test_empty_issues_returns_empty(self):
        result = self.agent.rank(issues=[])
        assert result == []

    def test_ranking_preserves_all_issues(self):
        """All input issues should be present in ranked output."""
        issues = [
            {"severity": "HIGH", "type": "long_method", "effort_to_fix": "HOURS"},
            {"severity": "LOW", "type": "missing_docstring", "effort_to_fix": "MINUTES"},
            {"severity": "CRITICAL", "type": "hardcoded_password", "effort_to_fix": "MINUTES"},
        ]
        with patch.object(self.agent, '_get_ai_enrichment', return_value=[]):
            ranked = self.agent.rank(issues)
        assert len(ranked) == 3

    def test_sprint_plan_grouping(self):
        ranked = [
            {"score": 90, "recommended_sprint": 1},
            {"score": 60, "recommended_sprint": 2},
            {"score": 20, "recommended_sprint": 3},
        ]
        plan = self.agent.get_sprint_plan(ranked)
        assert len(plan[1]) == 1
        assert len(plan[2]) == 1
        assert len(plan[3]) == 1


class TestFixProposalAgent:
    def setup_method(self):
        from agents.fix_proposal_agent import FixProposalAgent
        from tools.memory_bank import MemoryBank
        self.agent = FixProposalAgent(memory=MemoryBank())

    def test_template_available_for_bare_except(self):
        assert "bare_except" in self.agent._fix_templates

    def test_template_available_for_hardcoded_password(self):
        assert "hardcoded_password" in self.agent._fix_templates

    def test_template_available_for_no_tests(self):
        assert "no_tests" in self.agent._fix_templates

    def test_template_fix_has_required_fields(self):
        """All templates must have required fields."""
        required = {"issue_type", "severity", "problem_summary", "fix_summary", "before_code", "after_code", "steps", "testing_tip"}
        for name, template in self.agent._fix_templates.items():
            for field in required:
                assert field in template, f"Template '{name}' missing field '{field}'"

    def test_apply_template_adds_issue_metadata(self):
        issue = {"_rank_id": 42, "type": "bare_except", "severity": "MEDIUM", "location": "app.py:10", "score": 70, "priority": "HIGH"}
        proposal = self.agent._apply_template(issue, self.agent._fix_templates["bare_except"])
        assert proposal["issue_id"] == 42
        assert proposal["source"] == "template"
        assert proposal["original_issue"]["location"] == "app.py:10"

    def test_fallback_fix_always_works(self):
        issue = {"_rank_id": 1, "type": "unknown_type", "severity": "LOW", "location": "x.py:1"}
        fallback = self.agent._fallback_fix(issue)
        assert "steps" in fallback
        assert len(fallback["steps"]) > 0

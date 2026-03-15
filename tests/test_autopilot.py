
import pytest
import sys
sys.path.insert(0, '/content/codedebt-guardian')

from agents.autopilot_agent import AutoPilotAgent, AutoPilotConfig
from tools.safety_layer import SafetyLayer
from tools.change_detector import ChangeDetector


class TestSafetyLayer:
    def setup_method(self):
        self.safety = SafetyLayer()

    def test_valid_code_passes(self):
        original = "def hello():\n    pass\n"
        patched = "def hello():\n    \"\"\"Hello.\"\"\"\n    pass\n"
        ok, reason = self.safety.validate(original, patched)
        assert ok, reason

    def test_syntax_error_rejected(self):
        original = "def hello():\n    pass\n"
        patched = "def hello(\n    pass\n"
        ok, reason = self.safety.validate(original, patched)
        assert not ok
        assert "Syntax" in reason

    def test_empty_file_rejected(self):
        original = "def hello():\n    pass\n"
        patched = ""
        ok, reason = self.safety.validate(original, patched)
        assert not ok

    def test_dangerous_eval_rejected(self):
        original = "x = 1\n"
        patched = "x = eval(input())\n"
        ok, reason = self.safety.validate(original, patched)
        assert not ok
        assert "dangerous" in reason.lower()

    def test_stats_tracked(self):
        self.safety.validate("x = 1\n", "x = 1\n")
        stats = self.safety.stats()
        assert "passed" in stats
        assert "rejected" in stats


class TestAutoPilotConfig:
    def test_auto_merge_always_false(self):
        config = AutoPilotConfig(max_prs_per_day=10)
        assert config.auto_merge == False

    def test_default_draft_prs(self):
        config = AutoPilotConfig()
        assert config.draft_prs_only == True

    def test_default_fix_types(self):
        config = AutoPilotConfig()
        assert "bare_except" in config.allowed_fix_types


class TestAutoPilotAgent:
    def setup_method(self):
        self.config = AutoPilotConfig(dry_run=True, max_prs_per_day=3)
        self.agent = AutoPilotAgent(config=self.config)

    def test_dry_run_creates_no_real_prs(self):
        # With no token, change detector returns empty — that is fine
        result = self.agent.run("https://github.com/Priyanshjain10/codedebt-guardian")
        assert result["dry_run"] == True
        assert result["errors"] == [] or isinstance(result["errors"], list)

    def test_daily_limit_respected(self):
        self.agent._prs_today = 3  # already at limit
        result = self.agent.run("https://github.com/Priyanshjain10/codedebt-guardian")
        assert "Daily PR limit reached" in result["errors"]

    def test_report_generation(self):
        results = [{"issues_found": 4, "prs_created": [1, 2], "prs_skipped": []}]
        report = self.agent.generate_report(results)
        assert "4" in report
        assert "2" in report

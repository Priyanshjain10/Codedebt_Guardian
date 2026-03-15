"""
Schema Tests - Validates all Pydantic models behave correctly.
Tests validation, serialization, field coercion, and edge cases.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from models.schemas import (
    CodeLocation, TechnicalDebt, FixProposal, PullRequestInfo,
    RepoMetadata, DetectionResult, AnalysisSummary, AnalysisReport,
    DebtSeverity, DebtCategory, EffortLevel, Priority, DetectionSource,
)


class TestCodeLocation:
    def test_basic_creation(self):
        loc = CodeLocation(file_path="src/main.py", line_start=42)
        assert loc.file_path == "src/main.py"
        assert loc.line_start == 42

    def test_from_string_with_line(self):
        loc = CodeLocation.from_string("src/utils.py:17")
        assert loc.file_path == "src/utils.py"
        assert loc.line_start == 17

    def test_from_string_without_line(self):
        loc = CodeLocation.from_string("root")
        assert loc.file_path == "root"
        assert loc.line_start is None

    def test_to_string(self):
        loc = CodeLocation(file_path="src/main.py", line_start=10)
        assert loc.to_string() == "src/main.py:10"

    def test_to_string_no_line(self):
        loc = CodeLocation(file_path="src/main.py")
        assert loc.to_string() == "src/main.py"

    def test_invalid_line_range(self):
        with pytest.raises(ValidationError):
            CodeLocation(file_path="x.py", line_start=20, line_end=10)

    def test_valid_line_range(self):
        loc = CodeLocation(file_path="x.py", line_start=10, line_end=20)
        assert loc.line_end == 20


class TestTechnicalDebt:
    def _make_debt(self, **kwargs) -> TechnicalDebt:
        defaults = dict(
            type="bare_except",
            description="Bare except clause found",
            severity=DebtSeverity.MEDIUM,
            location=CodeLocation(file_path="test.py", line_start=5),
        )
        defaults.update(kwargs)
        return TechnicalDebt(**defaults)

    def test_basic_creation(self):
        debt = self._make_debt()
        assert debt.type == "bare_except"
        assert debt.severity == DebtSeverity.MEDIUM

    def test_auto_generates_id(self):
        d1 = self._make_debt()
        d2 = self._make_debt()
        assert d1.id != d2.id

    def test_auto_generates_title_from_type(self):
        debt = self._make_debt(type="long_method", title="")
        assert debt.title == "Long Method"

    def test_explicit_title_preserved(self):
        debt = self._make_debt(title="My Custom Title")
        assert debt.title == "My Custom Title"

    def test_empty_description_raises(self):
        with pytest.raises(ValidationError):
            self._make_debt(description="   ")

    def test_confidence_bounds(self):
        debt = self._make_debt(confidence=0.95)
        assert debt.confidence == 0.95
        with pytest.raises(ValidationError):
            self._make_debt(confidence=1.5)
        with pytest.raises(ValidationError):
            self._make_debt(confidence=-0.1)

    def test_defaults(self):
        debt = self._make_debt()
        assert debt.quick_win is False
        assert debt.blocks_other_work is False
        assert debt.recommended_sprint == 2
        assert debt.score is None
        assert debt.priority is None

    def test_severity_enum_values(self):
        for sev in DebtSeverity:
            debt = self._make_debt(severity=sev)
            assert debt.severity == sev

    def test_json_serializable(self):
        debt = self._make_debt()
        data = debt.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "id" in data
        assert "type" in data
        assert "severity" in data

    def test_roundtrip_serialization(self):
        debt = self._make_debt()
        data = debt.model_dump(mode="json")
        restored = TechnicalDebt.model_validate(data)
        assert restored.type == debt.type
        assert restored.description == debt.description


class TestFixProposal:
    def _make_fix(self, **kwargs) -> FixProposal:
        defaults = dict(
            issue_type="bare_except",
            severity=DebtSeverity.MEDIUM,
            problem_summary="Bare except swallows all exceptions",
            fix_summary="Replace with specific exception types",
        )
        defaults.update(kwargs)
        return FixProposal(**defaults)

    def test_basic_creation(self):
        fix = self._make_fix()
        assert fix.issue_type == "bare_except"

    def test_short_summary_raises(self):
        with pytest.raises(ValidationError):
            self._make_fix(problem_summary="Too short")

    def test_steps_strips_empty(self):
        fix = self._make_fix(steps=["Step 1", "", "  ", "Step 3"])
        assert len(fix.steps) == 2
        assert "Step 1" in fix.steps
        assert "Step 3" in fix.steps

    def test_empty_steps_allowed(self):
        fix = self._make_fix(steps=[])
        assert fix.steps == []

    def test_auto_id(self):
        f1 = self._make_fix()
        f2 = self._make_fix()
        assert f1.id != f2.id


class TestPullRequestInfo:
    def test_basic_creation(self):
        pr = PullRequestInfo(
            number=42,
            title="fix: resolve bare_except",
            html_url="https://github.com/owner/repo/pull/42",
            branch="codedebt/bare-except-fix",
        )
        assert pr.number == 42
        assert pr.state == "open"

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationError):
            PullRequestInfo(
                number=1,
                title="test",
                html_url="https://gitlab.com/owner/repo/pull/1",
                branch="fix-branch",
            )

    def test_invalid_pr_number(self):
        with pytest.raises(ValidationError):
            PullRequestInfo(number=0, title="t", html_url="https://github.com/x/y/pull/0", branch="b")


class TestAnalysisSummary:
    def test_basic(self):
        s = AnalysisSummary(total_issues=10, critical=2, high=4, medium=3, low=1)
        assert s.total_issues == 10

    def test_auto_fixes_total_if_too_low(self):
        # If critical+high+medium+low > total_issues, total_issues gets bumped
        s = AnalysisSummary(total_issues=3, critical=2, high=4, medium=3, low=1)
        assert s.total_issues >= 10


class TestAnalysisReport:
    def test_basic_creation(self):
        report = AnalysisReport(repo_url="https://github.com/owner/repo")
        assert report.repo_url == "https://github.com/owner/repo"
        assert isinstance(report.generated_at, datetime)
        assert report.id is not None

    def test_to_dict_and_back(self):
        report = AnalysisReport(
            repo_url="https://github.com/owner/repo",
            branch="main",
            summary=AnalysisSummary(total_issues=5, critical=1),
        )
        data = report.to_dict()
        assert isinstance(data, dict)
        assert data["repo_url"] == "https://github.com/owner/repo"

        restored = AnalysisReport.from_dict(data)
        assert restored.repo_url == report.repo_url
        assert restored.summary.total_issues == 5

    def test_unique_ids(self):
        r1 = AnalysisReport(repo_url="https://github.com/a/b")
        r2 = AnalysisReport(repo_url="https://github.com/a/b")
        assert r1.id != r2.id


class TestDebtDetectionAgentTypedConversion:
    """Test the typed conversion helper on the detection agent."""

    def setup_method(self):
        import sys
        sys.path.insert(0, ".")
        from agents.debt_detection_agent import DebtDetectionAgent
        from tools.memory_bank import MemoryBank
        self.agent = DebtDetectionAgent(memory=MemoryBank())

    def test_converts_valid_dict(self):
        raw = {
            "type": "bare_except",
            "description": "Bare except clause found",
            "severity": "MEDIUM",
            "location": "test.py:5",
            "effort_to_fix": "MINUTES",
            "source": "static_analysis",
        }
        result = self.agent._to_typed_issue(raw)
        assert isinstance(result, TechnicalDebt)
        assert result.type == "bare_except"
        assert result.severity == DebtSeverity.MEDIUM
        assert result.effort_to_fix == EffortLevel.MINUTES
        assert result.location.file_path == "test.py"
        assert result.location.line_start == 5

    def test_handles_unknown_severity(self):
        raw = {
            "type": "custom_issue",
            "description": "Some custom issue",
            "severity": "INVALID_LEVEL",
            "location": "app.py:10",
        }
        result = self.agent._to_typed_issue(raw)
        assert result.severity == DebtSeverity.MEDIUM  # Falls back to MEDIUM

    def test_handles_missing_optional_fields(self):
        raw = {
            "type": "missing_readme",
            "description": "No README found",
            "severity": "HIGH",
            "location": "root",
        }
        result = self.agent._to_typed_issue(raw)
        assert result.type == "missing_readme"
        assert result.impact == ""

    def test_batch_conversion_skips_invalid(self):
        raw_issues = [
            {"type": "bare_except", "description": "desc", "severity": "MEDIUM", "location": "x.py:1"},
            {"type": "bad_issue", "description": "", "severity": "LOW", "location": "y.py:2"},  # empty desc
            {"type": "long_method", "description": "long func", "severity": "HIGH", "location": "z.py:3"},
        ]
        results = self.agent.to_typed_results(raw_issues)
        # Empty description should be skipped, valid ones kept
        assert len(results) == 2
        types = [r.type for r in results]
        assert "bare_except" in types
        assert "long_method" in types

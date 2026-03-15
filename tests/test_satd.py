"""
Tests for the Advanced SATD (Self-Admitted Technical Debt) Detector.
All Gemini API calls are mocked so tests run fast and offline.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json


# ── Extraction Logic (no Gemini needed) ───────────────────────────────────────

class TestSATDAnchorExtraction:
    """Test regex-based anchor extraction for Python and JS comment styles."""

    def setup_method(self):
        from tools.satd_detector import SATDDetector
        self.detector = SATDDetector()

    def test_extract_anchors_finds_all_markers(self):
        """All 6 anchor types should be detected in Python-style comments."""
        code = """
import os
# TODO: refactor this later
x = 1
# FIXME: this is broken
y = 2
# HACK: temporary workaround
z = 3
# XXX: needs review
a = 4
# OPTIMIZE: slow query
b = 5
# DEBT: legacy coupling
c = 6
""".strip()
        lines = code.split("\n")
        anchors = self.detector._extract_anchors(lines)
        markers = [a[1].split(":")[0] for a in anchors]
        assert "TODO" in markers
        assert "FIXME" in markers
        assert "HACK" in markers
        assert "XXX" in markers
        assert "OPTIMIZE" in markers
        assert "DEBT" in markers
        assert len(anchors) == 6

    def test_extract_anchors_js_style_comments(self):
        """JS/TS-style (//) comments should also be detected."""
        code = """
const x = 1;
// TODO: migrate to new API
const y = 2;
// HACK: bypass auth for dev
const z = 3;
""".strip()
        lines = code.split("\n")
        anchors = self.detector._extract_anchors(lines)
        assert len(anchors) == 2
        assert anchors[0][1].startswith("TODO")
        assert anchors[1][1].startswith("HACK")

    def test_no_anchors_in_clean_code(self):
        """Code without SATD markers should return empty list."""
        code = "def clean():\n    return 42\n"
        lines = code.split("\n")
        anchors = self.detector._extract_anchors(lines)
        assert anchors == []

    def test_code_context_extraction(self):
        """Should grab the correct 15-line window after the anchor."""
        lines = [f"line_{i}" for i in range(30)]
        # Anchor at line 5 (1-based) → context should be lines[5:20] (0-indexed)
        ctx = self.detector._get_code_context(lines, anchor_line=5, window=15)
        context_lines = ctx.split("\n")
        assert context_lines[0] == "line_5"
        assert len(context_lines) == 15

    def test_code_context_near_end_of_file(self):
        """Context window near EOF should not crash, just return available lines."""
        lines = [f"line_{i}" for i in range(10)]
        ctx = self.detector._get_code_context(lines, anchor_line=8, window=15)
        context_lines = ctx.split("\n")
        assert len(context_lines) == 2  # lines[8] and lines[9]


# ── Full Scan with Mocked Gemini ──────────────────────────────────────────────

# ── Full Scan with Static Fallback ──────────────────────────────────────────────

class TestSATDScanStaticFallback:
    """Test the full scan pipeline with static keyword fallback."""

    def setup_method(self):
        from tools.satd_detector import SATDDetector
        self.detector = SATDDetector()

    def test_scan_with_static_fallback(self):
        """Full scan should return valid issue dicts using static keywords."""
        code = """import os
# HACK: bypassing validation for speed
def process(data):
    return data
"""
        issues = self.detector.scan(code, "processor.py")

        assert len(issues) == 1
        issue = issues[0]
        assert issue["type"] == "satd_design"
        assert issue["severity"] == "HIGH"  # 'hack' maps to HIGH
        assert "HACK" in issue["description"]
        assert issue["location"] == "processor.py:2"
        assert issue["source"] == "satd_analysis"
        assert issue["line"] == 2

    def test_false_positive_filtered(self):
        """Issues classified as False_Positive should be excluded."""
        code = """# TODO: add feature request for dark mode
def render():
    pass
"""
        issues = self.detector.scan(code, "ui.py")
        assert issues == []  # 'feature request' maps to False_Positive

    def test_multiple_anchors_classified_independently(self):
        """Each anchor should get its own static classification based on keywords."""
        code = """import os
# TODO: add input validation
def save(data):
    db.insert(data)

# FIXME: fix security auth bypass
def query(user_input):
    db.execute(f"SELECT * FROM t WHERE id={user_input}")
"""
        issues = self.detector.scan(code, "db.py")
        assert len(issues) == 2
        
        # TODO -> HIGH, no specific category keywords -> Design_Debt
        assert issues[0]["type"] == "satd_design"
        assert issues[0]["severity"] == "HIGH"
        
        # FIXME -> HIGH, 'fix'/'security'/'auth' -> Defect_Debt (defect takes precedence in if/elif block due to 'fix')
        assert issues[1]["type"] == "satd_defect"
        assert issues[1]["severity"] == "HIGH"

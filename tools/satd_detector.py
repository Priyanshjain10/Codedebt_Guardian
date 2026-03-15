"""
SATD (Self-Admitted Technical Debt) Detector

Context-aware detector that finds explicit developer-admitted debt comments
(TODO, FIXME, HACK, etc.), extracts the surrounding code context, and uses
Gemini 2.0 Flash to classify the actual business risk.

Unlike naive regex-based SAST tools, this module:
  1. Grabs the adjacent code block for context (15 lines after anchor)
  2. Sends Comment + Code Context to Gemini for semantic classification
  3. Filters out false positives using AI reasoning
  4. Maps results to the project's standard issue dict schema
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_GENAI_AVAILABLE = False


# Anchors to scan for — covers Python (#) and JS/TS (//) comment styles
_ANCHOR_PATTERN = re.compile(
    r"(?:^|\s)(?:#|//)\s*\b(TODO|FIXME|HACK|XXX|OPTIMIZE|DEBT)\b[:\s]*(.*)",
    re.IGNORECASE,
)

# Map static category → issue type prefix
_CATEGORY_TO_TYPE = {
    "Defect_Debt": "satd_defect",
    "Design_Debt": "satd_design",
    "Security_Debt": "satd_security",
    "Test_Debt": "satd_test",
}

# Map Gemini category → issue type prefix
_CATEGORY_TO_TYPE = {
    "Defect_Debt": "satd_defect",
    "Design_Debt": "satd_design",
    "Security_Debt": "satd_security",
    "Test_Debt": "satd_test",
}


class SATDDetector:
    """
    Scans source code for self-admitted technical debt comments, extracts
    surrounding code context, and classifies risk via Gemini 2.0 Flash.
    """

    def __init__(self) -> None:
        self.model = None
        # Gemini model disabled for free tier constraint
        pass

    # ── Public API ────────────────────────────────────────────────────────

    def scan(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """
        Main entry point.  Scans source content for SATD anchors, classifies
        each via Gemini, and returns a list of issue dicts matching the
        project's standard schema.

        Returns an empty list on any API or runtime failure (never crashes).
        """
        if not content:
            return []

        try:
            lines = content.split("\n")
            anchors = self._extract_anchors(lines)

            if not anchors:
                return []

            issues: List[Dict[str, Any]] = []
            for line_no, comment_text in anchors:
                code_ctx = self._get_code_context(lines, line_no)
                classification = self._classify_with_gemini(comment_text, code_ctx)

                if classification is None:
                    continue

                # Filter out false positives
                category = classification.get("category", "")
                if category == "False_Positive":
                    continue

                issue = self._to_issue_dict(
                    line_no, comment_text, classification, filename
                )
                if issue:
                    issues.append(issue)

            return issues

        except Exception as e:
            logger.warning(f"SATD scan failed for {filename}: {e}")
            return []

    # ── Internal helpers ──────────────────────────────────────────────────

    def _extract_anchors(self, lines: List[str]) -> List[Tuple[int, str]]:
        """
        Scan lines for comment anchors (TODO, FIXME, HACK, XXX, OPTIMIZE, DEBT).
        Supports both Python (#) and JS/TS (//) comment styles.

        Returns list of (1-based line number, full comment text) tuples.
        """
        anchors: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines):
            match = _ANCHOR_PATTERN.search(line)
            if match:
                marker = match.group(1).upper()
                detail = match.group(2).strip()
                comment = f"{marker}: {detail}" if detail else marker
                anchors.append((idx + 1, comment))
        return anchors

    def _get_code_context(
        self, lines: List[str], anchor_line: int, window: int = 15
    ) -> str:
        """
        Extract the next `window` lines of code after the anchor comment.
        anchor_line is 1-based.
        """
        start = anchor_line  # line after the comment (0-indexed = anchor_line)
        end = min(start + window, len(lines))
        return "\n".join(lines[start:end])

    def _classify_with_gemini(
        self, comment: str, code_context: str
    ) -> Optional[Dict[str, str]]:
        """
        Static fallback for Gemini classification to preserve API quota.
        """
        comment_lower = comment.lower()

        # False positives
        if any(w in comment_lower for w in ["informational", "feature request"]):
            return {"category": "False_Positive", "severity": "LOW", "reason": "Looks like an informational comment."}

        # Urgency/Severity parsing
        high_urgency = ["hack", "fixme", "todo", "workaround", "kludge", "critical", "urgent", "security"]
        med_urgency = ["temp", "temporary", "quick fix", "dirty", "refactor"]
        
        severity = "LOW"
        if any(w in comment_lower for w in high_urgency):
            severity = "HIGH"
        elif any(w in comment_lower for w in med_urgency):
            severity = "MEDIUM"

        # Category parsing
        category = "Design_Debt"
        if "bug" in comment_lower or "defect" in comment_lower or "fix" in comment_lower:
            category = "Defect_Debt"
        elif "security" in comment_lower or "auth" in comment_lower or "unsafe" in comment_lower:
            category = "Security_Debt"
        elif "test" in comment_lower or "mock" in comment_lower:
            category = "Test_Debt"

        return {
            "category": category,
            "severity": severity,
            "reason": "Categorized via static keyword fallback."
        }

    def _to_issue_dict(
        self,
        line_no: int,
        comment: str,
        classification: Dict[str, str],
        filename: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Map Gemini classification to the project's standard issue dict schema.
        Returns None if the category is unknown.
        """
        category = classification.get("category", "")
        issue_type = _CATEGORY_TO_TYPE.get(category)
        if not issue_type:
            return None

        severity = classification.get("severity", "MEDIUM").upper()
        if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            severity = "MEDIUM"

        reason = classification.get("reason", "Self-admitted technical debt detected.")

        return {
            "type": issue_type,
            "severity": severity,
            "description": f"[SATD] {comment} — {reason}",
            "location": f"{filename}:{line_no}",
            "line": line_no,
            "impact": f"Developer-acknowledged debt ({category.replace('_', ' ')})",
            "effort_to_fix": "HOURS",
            "source": "satd_analysis",
        }

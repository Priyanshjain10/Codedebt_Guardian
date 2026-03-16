"""
Debt Detection Agent - Agent 1 of 3
Scans codebases for technical debt using AST analysis + Gemini AI.

Detects:
- Code smells (long methods, duplicate code, god classes)
- Security vulnerabilities
- Outdated dependencies
- Missing documentation
- Complex cyclomatic complexity
- Anti-patterns
"""

import ast
import os
import re
import logging
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai

    _GENAI_AVAILABLE = True
except ImportError:
    genai = None
    _GENAI_AVAILABLE = False

from tools.github_tool import GitHubTool
from tools.code_analyzer import CodeAnalyzer
from tools.memory_bank import MemoryBank
from tools.observability import ObservabilityLayer
from models.schemas import (
    TechnicalDebt,
    CodeLocation,
    DebtSeverity,
    EffortLevel,
    DetectionSource,
)

logger = logging.getLogger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when Gemini API quota is exhausted after all retry attempts."""

    pass


try:
    from tools.js_analyzer import JavaScriptAnalyzer

    _js_analyzer = JavaScriptAnalyzer()
    JS_SUPPORT = True
except ImportError:
    JS_SUPPORT = False

try:
    from tools.satd_detector import SATDDetector

    _SATD_AVAILABLE = True
except ImportError:
    _SATD_AVAILABLE = False

try:
    from groq import Groq

    _GROQ_AVAILABLE = bool(os.environ.get("GROQ_API_KEY"))
except ImportError:
    _GROQ_AVAILABLE = False

# Configure Gemini
# Initialization moved inside __init__ to prevent module-level execution issues
if _GENAI_AVAILABLE:
    pass

SYSTEM_PROMPT = """You are an expert software engineer specializing in technical debt detection.
Analyze the provided code and identify ALL instances of technical debt including:
1. Code smells (long methods >50 lines, duplicate code, large classes >500 lines)
2. Security vulnerabilities (hardcoded credentials, SQL injection risks, unsafe deserialization)
3. Performance issues (N+1 queries, inefficient algorithms, memory leaks)
4. Maintainability issues (missing error handling, no type hints, poor naming)
5. Documentation debt (missing docstrings, outdated comments, no README)
6. Dependency issues (outdated packages, deprecated APIs, circular imports)

For each issue found, provide:
- type: category of debt
- severity: CRITICAL/HIGH/MEDIUM/LOW
- description: clear explanation of the problem
- location: file and line number if applicable
- impact: business/technical impact
- effort_to_fix: MINUTES/HOURS/DAYS

Respond ONLY with valid JSON array of issues."""


class DebtDetectionAgent:
    """
    Agent 1: Technical Debt Detection

    Uses a hybrid approach:
    1. Static analysis via Python AST for structural metrics
    2. Gemini AI for semantic understanding and context-aware detection
    3. GitHub API for dependency and metadata analysis
    """

    def __init__(self, memory: Optional[MemoryBank] = None):
        if _GENAI_AVAILABLE:
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
        else:
            self.model = None

        self.github = GitHubTool()
        self.analyzer = CodeAnalyzer()
        self.memory = memory or MemoryBank()
        self.obs = ObservabilityLayer(service_name="debt_detection_agent")
        self.token_usage = {
            "input": 0,
            "output": 0,
            "model_usage": {"groq": 0, "gemini": 0},
        }

        # SATD detector (graceful — None if unavailable)
        self.satd_detector = SATDDetector() if _SATD_AVAILABLE else None

        # Context engineering: conversation history for multi-turn analysis
        self._chat_history: List[Dict] = []

    def analyze(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Main analysis method. Fetches repo content and runs full debt detection.

        Args:
            repo_url: GitHub repository URL
            branch: branch to analyze

        Returns:
            Dict with detected issues, metadata, and statistics
        """
        with self.obs.trace("analyze") as span:
            span.set_attribute("repo_url", repo_url)

            logger.info(f"Starting debt detection for {repo_url}")

            # Step 1: Fetch repository content
            repo_data = self.github.fetch_repo_contents(repo_url, branch)
            python_files = [f for f in repo_data["files"] if f["name"].endswith(".py")]
            js_files = [
                f
                for f in repo_data["files"]
                if f["name"].endswith((".js", ".ts", ".jsx", ".tsx"))
            ]

            all_issues = []
            files_scanned = 0

            # Step 2a: Static AST analysis on Python files
            for file_info in python_files[:20]:  # Limit to 20 files per run
                static_issues = self._run_static_analysis(file_info)
                all_issues.extend(static_issues)
                files_scanned += 1

            # Step 2b: JS/TS analysis (if analyzer is available)
            if JS_SUPPORT:
                for file_info in js_files[:15]:
                    try:
                        js_issues = _js_analyzer.analyze(file_info)
                        all_issues.extend(js_issues)
                        files_scanned += 1
                    except Exception as e:
                        logger.warning(
                            f"JS analysis failed for {file_info.get('name')}: {e}"
                        )
                    # SATD scanning on JS/TS files (handles // comment style)
                    if self.satd_detector:
                        try:
                            js_content = GitHubTool.read_file_content(file_info)
                            satd_issues = self.satd_detector.scan(
                                js_content, file_info.get("name", "")
                            )
                            all_issues.extend(satd_issues)
                        except Exception as e:
                            logger.warning(
                                f"SATD scan failed for JS file {file_info.get('name')}: {e}"
                            )

            # Step 3: AI-powered semantic analysis
            files_with_issues = {
                iss.get("location", "").split(":")[0]
                for iss in all_issues
                if iss.get("location")
            }
            ai_files = [f for f in python_files if f.get("name") in files_with_issues][
                :10
            ]
            ai_issues = self._run_ai_analysis(ai_files, repo_data["repo_metadata"])
            all_issues.extend(ai_issues)

            # Step 4: Dependency analysis
            dep_issues = self._analyze_dependencies(repo_data)
            all_issues.extend(dep_issues)

            # Step 5: Documentation debt
            doc_issues = self._analyze_documentation(repo_data, python_files)
            all_issues.extend(doc_issues)

            # Deduplicate issues
            all_issues = self._deduplicate(all_issues)

            result = {
                "repo_url": repo_url,
                "branch": branch,
                "repo_metadata": repo_data["repo_metadata"],
                "files_scanned": files_scanned,
                "total_issues": len(all_issues),
                "issues": all_issues,
                "stats": self._compute_stats(all_issues),
                "_temp_dir": repo_data.get("_temp_dir"),
            }

            span.set_attribute("total_issues", len(all_issues))
            logger.info(f"Detection complete: {len(all_issues)} issues found")
            return result

    def _run_static_analysis(self, file_info: Dict) -> List[Dict]:
        """Run AST-based static analysis on a Python file."""
        issues = []
        content = GitHubTool.read_file_content(file_info)
        filename = file_info.get("name", "unknown")

        if not content:
            return issues

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            issues.append(
                {
                    "type": "syntax_error",
                    "severity": "CRITICAL",
                    "description": f"Syntax error in file: {str(e)}",
                    "location": f"{filename}:{e.lineno}",
                    "impact": "File cannot be executed",
                    "effort_to_fix": "MINUTES",
                    "source": "static_analysis",
                }
            )
            return issues

        lines = content.split("\n")
        total_lines = len(lines)

        # Check for overly long files
        if total_lines > 500:
            issues.append(
                {
                    "type": "god_file",
                    "severity": "HIGH",
                    "description": f"File has {total_lines} lines. Files over 500 lines are hard to maintain.",
                    "location": filename,
                    "impact": "Reduced readability and maintainability",
                    "effort_to_fix": "DAYS",
                    "source": "static_analysis",
                    "metric": total_lines,
                }
            )

        for node in ast.walk(tree):
            # Detect long functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = (node.end_lineno or 0) - node.lineno
                if func_lines > 50:
                    issues.append(
                        {
                            "type": "long_method",
                            "severity": "MEDIUM" if func_lines < 100 else "HIGH",
                            "description": f"Function '{node.name}' is {func_lines} lines long (max recommended: 50)",
                            "location": f"{filename}:{node.lineno}",
                            "impact": "Hard to test, understand, and maintain",
                            "effort_to_fix": "HOURS",
                            "source": "static_analysis",
                            "metric": func_lines,
                        }
                    )

                # Check for missing docstrings
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                ):
                    if func_lines > 10:  # Only flag non-trivial functions
                        issues.append(
                            {
                                "type": "missing_docstring",
                                "severity": "LOW",
                                "description": f"Function '{node.name}' has no docstring",
                                "location": f"{filename}:{node.lineno}",
                                "impact": "Reduces code discoverability and maintainability",
                                "effort_to_fix": "MINUTES",
                                "source": "static_analysis",
                            }
                        )

                # Check for too many parameters
                args_count = len(node.args.args)
                if args_count > 7:
                    issues.append(
                        {
                            "type": "too_many_parameters",
                            "severity": "MEDIUM",
                            "description": f"Function '{node.name}' has {args_count} parameters (max recommended: 7)",
                            "location": f"{filename}:{node.lineno}",
                            "impact": "Hard to call, test and understand",
                            "effort_to_fix": "HOURS",
                            "source": "static_analysis",
                            "metric": args_count,
                        }
                    )

            # Detect large classes
            if isinstance(node, ast.ClassDef):
                class_lines = (node.end_lineno or 0) - node.lineno
                method_count = sum(
                    1 for n in ast.walk(node) if isinstance(n, ast.FunctionDef)
                )
                if class_lines > 300 or method_count > 20:
                    issues.append(
                        {
                            "type": "god_class",
                            "severity": "HIGH",
                            "description": f"Class '{node.name}' has {class_lines} lines and {method_count} methods",
                            "location": f"{filename}:{node.lineno}",
                            "impact": "Violates Single Responsibility Principle, hard to maintain",
                            "effort_to_fix": "DAYS",
                            "source": "static_analysis",
                            "metric": {"lines": class_lines, "methods": method_count},
                        }
                    )

        # Detect hardcoded credentials
        credential_patterns = [
            (r'(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "hardcoded_password"),
            (
                r'(api_key|apikey|secret_key)\s*=\s*["\'][^"\']+["\']',
                "hardcoded_api_key",
            ),
            (r'(token)\s*=\s*["\'][A-Za-z0-9+/]{20,}["\']', "hardcoded_token"),
        ]
        for i, line in enumerate(lines, 1):
            for pattern, debt_type in credential_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(
                        {
                            "type": debt_type,
                            "severity": "CRITICAL",
                            "description": "Possible hardcoded credential detected",
                            "location": f"{filename}:{i}",
                            "impact": "Security vulnerability - credentials may be exposed in version control",
                            "effort_to_fix": "MINUTES",
                            "source": "static_analysis",
                        }
                    )

        # Detect bare except clauses
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(
                    {
                        "type": "bare_except",
                        "severity": "MEDIUM",
                        "description": "Bare `except:` clause catches all exceptions including SystemExit and KeyboardInterrupt",
                        "location": f"{filename}:{node.lineno}",
                        "impact": "Can hide bugs, makes debugging very difficult",
                        "effort_to_fix": "MINUTES",
                        "source": "static_analysis",
                    }
                )

        # SATD: Scan for self-admitted technical debt comments
        if self.satd_detector:
            try:
                satd_issues = self.satd_detector.scan(content, filename)
                issues.extend(satd_issues)
            except Exception as e:
                logger.warning(f"SATD scan failed for {filename}: {e}")

        return issues

    def _run_ai_analysis(self, files: List[Dict], repo_metadata: Dict) -> List[Dict]:
        """Use Gemini to perform semantic, context-aware debt analysis."""
        if not self.model or not files:
            return []

        import time
        import json

        all_ai_issues = []

        files_to_analyze = [f for f in files if f.get("issues")][:10]

        for f in files_to_analyze:
            content = GitHubTool.read_file_content(f)
            if not content:
                continue

            prompt = f"""Analyze this codebase for technical debt.

Repository: {repo_metadata.get("name", "Unknown")}
Language: {repo_metadata.get("language", "Python")}

Code to analyze:
{f.get("name", "Unknown")}
```
{content[:10000]}
```

Find all technical debt issues. Focus on what a senior engineer would flag in code review."""

            file_issues = []

            # Try Groq first (primary provider)
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key and _GROQ_AVAILABLE:
                try:
                    client = Groq(api_key=groq_key)

                    plain_text_prompt = (
                        prompt
                        + """\n
Instead of JSON, provide your response in EXACTLY this plain text format for each issue found. Separate each issue with '---':
TYPE: <category of debt>
SEVERITY: <CRITICAL/HIGH/MEDIUM/LOW>
DESC: <clear explanation>
LOC: <file and line number>
IMPACT: <business/technical impact>
EFFORT: <MINUTES/HOURS/DAYS>
---"""
                    )
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": plain_text_prompt}],
                        temperature=0.1,
                        max_tokens=4000,
                    timeout=60,
                    )

                    # Record Groq tokens
                    if hasattr(response, "usage"):
                        _in = getattr(response.usage, "prompt_tokens", 0)
                        _out = getattr(response.usage, "completion_tokens", 0)
                        self.token_usage["input"] += _in
                        self.token_usage["output"] += _out
                        self.token_usage["model_usage"]["groq"] += _in + _out

                    raw = response.choices[0].message.content.strip()
                    temp_issues = []
                    current_issue = {}

                    for line in raw.split("\n"):
                        line = line.strip()
                        if line == "---" or line.startswith("---"):
                            if "type" in current_issue:
                                current_issue["source"] = "groq_ai"
                                temp_issues.append(current_issue)
                            current_issue = {}
                        elif line.startswith("TYPE:"):
                            current_issue["type"] = line[5:].strip()
                        elif line.startswith("SEVERITY:"):
                            current_issue["severity"] = line[9:].strip()
                        elif line.startswith("DESC:"):
                            current_issue["description"] = line[5:].strip()
                        elif line.startswith("LOC:"):
                            current_issue["location"] = line[4:].strip()
                        elif line.startswith("IMPACT:"):
                            current_issue["impact"] = line[7:].strip()
                        elif line.startswith("EFFORT:"):
                            current_issue["effort_to_fix"] = line[7:].strip()

                    if current_issue and "type" in current_issue:
                        current_issue["source"] = "groq_ai"
                        temp_issues.append(current_issue)

                    if temp_issues:
                        file_issues = temp_issues

                    all_ai_issues.extend(file_issues)
                    continue  # skip Gemini for this file
                except Exception as e:
                    logger.warning(
                        f"Groq failed for {f.get('name')}: {e}, falling back to Gemini"
                    )

            # Gemini fallback
            for attempt in range(3):
                try:
                    chat = self.model.start_chat(history=self._chat_history)
                    response = chat.send_message(prompt)
                    self._chat_history = chat.history[-4:]

                    # Record Gemini tokens
                    if hasattr(response, "usage_metadata"):
                        _in = getattr(response.usage_metadata, "prompt_token_count", 0)
                        _out = getattr(
                            response.usage_metadata, "candidates_token_count", 0
                        )
                        self.token_usage["input"] += _in
                        self.token_usage["output"] += _out
                        self.token_usage["model_usage"]["gemini"] += _in + _out

                    raw = response.text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]

                    issues = json.loads(raw)
                    if isinstance(issues, list):
                        for issue in issues:
                            issue["source"] = "gemini_ai"
                        file_issues = issues
                    break  # Success
                except Exception as e:
                    err_str = str(e).lower()
                    if "429" in err_str or "quota" in err_str:
                        if attempt < 2:
                            time.sleep(5)
                        else:
                            logger.warning(
                                f"AI analysis failed for {f.get('name')}: {e}"
                            )
                            raise QuotaExhaustedError(
                                f"Gemini quota exhausted for {f.get('name')}"
                            )
                    else:
                        break  # Skip file silently on other errors

            all_ai_issues.extend(file_issues)

        return all_ai_issues

    def _analyze_dependencies(self, repo_data: Dict) -> List[Dict]:
        """Analyze requirements.txt and setup.py for dependency debt."""
        issues = []

        req_file = next(
            (
                f
                for f in repo_data["files"]
                if f["name"] in ["requirements.txt", "setup.py", "pyproject.toml"]
            ),
            None,
        )
        if not req_file:
            issues.append(
                {
                    "type": "missing_requirements",
                    "severity": "HIGH",
                    "description": "No requirements.txt or pyproject.toml found",
                    "location": "root",
                    "impact": "Project cannot be reliably reproduced or deployed",
                    "effort_to_fix": "HOURS",
                    "source": "dependency_analysis",
                }
            )
            return issues

        content = GitHubTool.read_file_content(req_file)

        # Check for unpinned dependencies
        unpinned = []
        for line in content.split("\n"):
            line = line.strip()
            if (
                line
                and not line.startswith("#")
                and "==" not in line
                and ">=" not in line
                and not line.startswith("-")
            ):
                unpinned.append(line)

        if unpinned:
            issues.append(
                {
                    "type": "unpinned_dependencies",
                    "severity": "MEDIUM",
                    "description": f"Unpinned dependencies found: {', '.join(unpinned[:5])}",
                    "location": req_file["name"],
                    "impact": "Builds may break unexpectedly when packages update",
                    "effort_to_fix": "MINUTES",
                    "source": "dependency_analysis",
                }
            )

        return issues

    def _analyze_documentation(
        self, repo_data: Dict, python_files: List[Dict]
    ) -> List[Dict]:
        """Analyze documentation completeness."""
        issues = []

        # Check for README
        readme = next(
            (f for f in repo_data["files"] if f["name"].upper().startswith("README")),
            None,
        )
        if not readme:
            issues.append(
                {
                    "type": "missing_readme",
                    "severity": "HIGH",
                    "description": "No README file found in repository",
                    "location": "root",
                    "impact": "Project is unapproachable for new contributors",
                    "effort_to_fix": "HOURS",
                    "source": "documentation_analysis",
                }
            )

        # Check for tests
        test_files = [f for f in repo_data["files"] if "test" in f["name"].lower()]
        if not test_files:
            issues.append(
                {
                    "type": "no_tests",
                    "severity": "HIGH",
                    "description": "No test files detected in repository",
                    "location": "root",
                    "impact": "Cannot verify correctness, regressions go undetected",
                    "effort_to_fix": "DAYS",
                    "source": "documentation_analysis",
                }
            )

        # Check for CI/CD
        ci_files = [
            f
            for f in repo_data["files"]
            if ".github" in f["name"] or "ci" in f["name"].lower()
        ]
        if not ci_files:
            issues.append(
                {
                    "type": "no_cicd",
                    "severity": "MEDIUM",
                    "description": "No CI/CD configuration found",
                    "location": "root",
                    "impact": "Manual deployments are error-prone and slow",
                    "effort_to_fix": "HOURS",
                    "source": "documentation_analysis",
                }
            )

        return issues

    def _deduplicate(self, issues: List[Dict]) -> List[Dict]:
        """Remove duplicate issues based on type + location."""
        seen = set()
        unique = []
        for issue in issues:
            key = f"{issue.get('type')}_{issue.get('location')}"
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique

    def _compute_stats(self, issues: List[Dict]) -> Dict:
        """Compute summary statistics over detected issues."""
        by_severity = {}
        by_type = {}
        by_source = {}

        for issue in issues:
            sev = issue.get("severity", "UNKNOWN")
            typ = issue.get("type", "unknown")
            src = issue.get("source", "unknown")

            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[typ] = by_type.get(typ, 0) + 1
            by_source[src] = by_source.get(src, 0) + 1

        return {
            "by_severity": by_severity,
            "by_type": by_type,
            "by_source": by_source,
        }

    def _to_typed_issue(self, raw: Dict) -> TechnicalDebt:
        """
        Convert a raw dict issue into a validated TechnicalDebt Pydantic model.
        Gracefully handles missing or mismatched fields.
        """
        location_str = raw.get("location", "unknown")
        location = CodeLocation.from_string(location_str)

        # Normalize severity
        raw_severity = raw.get("severity", "MEDIUM").upper()
        try:
            severity = DebtSeverity(raw_severity)
        except ValueError:
            severity = DebtSeverity.MEDIUM

        # Normalize effort
        raw_effort = raw.get("effort_to_fix", "HOURS").upper()
        try:
            effort = EffortLevel(raw_effort)
        except ValueError:
            effort = EffortLevel.HOURS

        # Normalize source
        raw_source = raw.get("source", "static_analysis")
        try:
            source = DetectionSource(raw_source)
        except ValueError:
            source = DetectionSource.STATIC_ANALYSIS

        return TechnicalDebt(
            type=raw.get("type", "unknown"),
            description=raw.get("description", "Technical debt detected"),
            severity=severity,
            location=location,
            impact=raw.get("impact", ""),
            effort_to_fix=effort,
            source=source,
            confidence=raw.get("confidence", 0.85),
        )

    def to_typed_results(self, raw_issues: List[Dict]) -> List[TechnicalDebt]:
        """Convert a list of raw dicts to validated TechnicalDebt models."""
        typed = []
        for raw in raw_issues:
            try:
                typed.append(self._to_typed_issue(raw))
            except Exception as e:
                logger.warning(f"Skipping invalid issue {raw.get('type')}: {e}")
        return typed

"""
JavaScript static analyzer using esprima AST parsing.
Detects common technical debt patterns in JS/TS files.
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False
    logger.warning("esprima not installed - JS analysis unavailable")


class JavaScriptAnalyzer:
    """AST-based static analyzer for JavaScript files."""

    MAX_FUNCTION_LINES = 50

    def analyze(self, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze a JS file and return list of debt issues."""
        from tools.github_tool import GitHubTool
        name = file_info.get("name", "")
        content = GitHubTool.read_file_content(file_info)
        path = file_info.get("path", name)

        if not content or not name.endswith((".js", ".ts", ".jsx", ".tsx")):
            return []

        issues = []
        issues.extend(self._regex_checks(content, path))

        if ESPRIMA_AVAILABLE:
            try:
                tree = esprima.parseScript(content, tolerant=True, loc=True)
                issues.extend(self._ast_checks(tree, path))
            except Exception as e:
                logger.debug(f"AST parse failed for {name}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for i in issues:
            key = (i.get("type"), i.get("location"))
            if key not in seen:
                seen.add(key)
                unique.append(i)

        return unique

    def _regex_checks(self, content: str, path: str) -> List[Dict]:
        """Fast regex-based checks that don't need AST."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # console.log left in production
            if re.search(r'console\.(log|debug|warn|error)\(', stripped):
                if not stripped.startswith("//"):
                    issues.append({
                        "type": "console_log",
                        "severity": "MEDIUM",
                        "location": f"{path}:{i}",
                        "description": "console.log left in production code",
                        "line": i,
                    })

            # var instead of const/let
            if re.match(r'\s*var\s+', line) and not stripped.startswith("//"):
                issues.append({
                    "type": "var_declaration",
                    "severity": "LOW",
                    "location": f"{path}:{i}",
                    "description": "Use const or let instead of var",
                    "line": i,
                })

            # Hardcoded credentials
            if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']',
                         stripped, re.IGNORECASE):
                if not stripped.startswith("//") and not stripped.startswith("*"):
                    issues.append({
                        "type": "hardcoded_password",
                        "severity": "CRITICAL",
                        "location": f"{path}:{i}",
                        "description": "Possible hardcoded credential detected",
                        "line": i,
                    })

            # Promise without .catch()
            if ".then(" in stripped and ".catch(" not in stripped and "await" not in stripped:
                issues.append({
                    "type": "unhandled_promise",
                    "severity": "HIGH",
                    "location": f"{path}:{i}",
                    "description": "Promise .then() without .catch() - unhandled rejection",
                    "line": i,
                })

        return issues

    def _ast_checks(self, tree, path: str) -> List[Dict]:
        """AST-based checks using esprima parse tree."""
        issues = []

        def walk(node):
            if node is None:
                return
            node_type = getattr(node, "type", None)

            # Long functions
            if node_type in ("FunctionDeclaration", "FunctionExpression",
                             "ArrowFunctionExpression"):
                loc = getattr(node, "loc", None)
                if loc:
                    start = loc.start.line
                    end = loc.end.line
                    length = end - start
                    if length > self.MAX_FUNCTION_LINES:
                        name = getattr(getattr(node, "id", None), "name", "anonymous")
                        issues.append({
                            "type": "long_method",
                            "severity": "HIGH" if length > 100 else "MEDIUM",
                            "location": f"{path}:{start}",
                            "description": f"Function '{name}' is {length} lines long (max: {self.MAX_FUNCTION_LINES})",
                            "line": start,
                        })

            # Callback hell - deeply nested callbacks
            if node_type == "CallExpression":
                args = getattr(node, "arguments", [])
                for arg in args:
                    if getattr(arg, "type", "") in ("FunctionExpression", "ArrowFunctionExpression"):
                        body = getattr(arg, "body", None)
                        if body:
                            inner_calls = _count_nested_callbacks(body)
                            if inner_calls >= 2:
                                loc = getattr(node, "loc", None)
                                line = loc.start.line if loc else 0
                                issues.append({
                                    "type": "callback_hell",
                                    "severity": "HIGH",
                                    "location": f"{path}:{line}",
                                    "description": f"Nested callbacks detected ({inner_calls} levels) - use async/await",
                                    "line": line,
                                })

            # Walk children
            for key in node.__dict__:
                child = getattr(node, key)
                if hasattr(child, "type"):
                    walk(child)
                elif isinstance(child, list):
                    for item in child:
                        if hasattr(item, "type"):
                            walk(item)

        def _count_nested_callbacks(node, depth=0):
            if depth > 5:
                return depth
            count = 0
            for key in node.__dict__:
                child = getattr(node, key)
                if hasattr(child, "type"):
                    if getattr(child, "type", "") in ("FunctionExpression", "ArrowFunctionExpression"):
                        count = max(count, _count_nested_callbacks(child, depth + 1) + 1)
                elif isinstance(child, list):
                    for item in child:
                        if hasattr(item, "type"):
                            if getattr(item, "type", "") in ("FunctionExpression", "ArrowFunctionExpression"):
                                count = max(count, _count_nested_callbacks(item, depth + 1) + 1)
            return count

        walk(tree)
        return issues

"""
Code Analyzer - Computes code quality metrics from Python source.
Used by the Debt Detection Agent for static analysis.
"""

import ast
import re
from typing import Any, Dict, List


class CodeAnalyzer:
    """Computes static code metrics from Python source files."""

    def compute_metrics(self, source_code: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Compute a set of code quality metrics for a Python file.

        Args:
            source_code: Raw Python source code
            filename: File path for reporting

        Returns:
            Dict of metrics
        """
        metrics = {
            "filename": filename,
            "lines_of_code": 0,
            "blank_lines": 0,
            "comment_lines": 0,
            "functions": [],
            "classes": [],
            "imports": [],
            "cyclomatic_complexity": 0,
            "has_type_hints": False,
            "parse_error": None,
        }

        lines = source_code.split("\n")
        metrics["lines_of_code"] = len(lines)
        metrics["blank_lines"] = sum(1 for l in lines if not l.strip())
        metrics["comment_lines"] = sum(1 for l in lines if l.strip().startswith("#"))

        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            metrics["parse_error"] = str(e)
            return metrics

        # Extract function info
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = (node.end_lineno or node.lineno) - node.lineno
                has_hints = bool(node.returns or any(a.annotation for a in node.args.args))
                metrics["functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "lines": func_lines,
                    "args_count": len(node.args.args),
                    "has_docstring": self._has_docstring(node),
                    "has_type_hints": has_hints,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
                if has_hints:
                    metrics["has_type_hints"] = True

            elif isinstance(node, ast.ClassDef):
                class_lines = (node.end_lineno or node.lineno) - node.lineno
                method_count = sum(1 for n in ast.walk(node) if isinstance(n, ast.FunctionDef))
                metrics["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "lines": class_lines,
                    "method_count": method_count,
                    "has_docstring": self._has_docstring(node),
                })

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        metrics["imports"].append(alias.name)
                else:
                    module = node.module or ""
                    metrics["imports"].append(module)

        # Cyclomatic complexity approximation
        metrics["cyclomatic_complexity"] = self._compute_complexity(tree)

        return metrics

    def _has_docstring(self, node: ast.AST) -> bool:
        """Check if a function or class has a docstring."""
        return (
            bool(node.body)
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

    def _compute_complexity(self, tree: ast.AST) -> int:
        """Approximate cyclomatic complexity by counting decision points."""
        complexity = 1  # Base
        decision_nodes = (
            ast.If, ast.While, ast.For, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension,
        )
        for node in ast.walk(tree):
            if isinstance(node, decision_nodes):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        return complexity

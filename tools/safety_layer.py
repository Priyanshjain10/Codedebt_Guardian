
""" Safety Layer — validates every code fix before a PR is created. """
import ast, logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class SafetyLayer:
    def __init__(self):
        self.passed = 0
        self.rejected = 0

    def validate(self, original_code: str, patched_code: str, filename: str = "unknown.py") -> Tuple[bool, str]:
        checks = [self._check_syntax, self._check_not_empty, self._check_no_dangerous_patterns]
        for check in checks:
            passed, reason = check(original_code, patched_code, filename)
            if not passed:
                self.rejected += 1
                logger.warning(f"Safety FAILED {filename}: {reason}")
                return False, reason
        self.passed += 1
        return True, "All checks passed"

    def _check_syntax(self, original, patched, filename):
        try:
            ast.parse(patched)
            return True, "Syntax OK"
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"

    def _check_not_empty(self, original, patched, filename):
        if len(patched.strip()) == 0:
            return False, "Patched file is empty"
        if len(patched) < len(original) * 0.5:
            return False, f"File suspiciously small after patch"
        return True, "Size OK"

    def _check_no_dangerous_patterns(self, original, patched, filename):
        import ast as _ast
        try:
            tree = _ast.parse(patched)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call):
                    if isinstance(node.func, _ast.Attribute):
                        if node.func.attr in ["system", "popen", "execv", "execve"]:
                            return False, f"Dangerous call: {node.func.attr}"
                    elif isinstance(node.func, _ast.Name):
                        if node.func.id in ["eval", "exec", "compile"]:
                            return False, f"Dangerous call: {node.func.id}"
        except SyntaxError:
            pass
        return True, "No dangerous patterns"

    def validate_structure(self, original: str, patched: str) -> Tuple[bool, str]:
        try:
            orig_tree = ast.parse(original)
            patch_tree = ast.parse(patched)
            orig_names = {n.name for n in ast.walk(orig_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
            patch_names = {n.name for n in ast.walk(patch_tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
            missing = orig_names - patch_names
            if missing:
                return False, f"Fix removed: {missing}"
            return True, "Structure preserved"
        except SyntaxError as e:
            return False, str(e)

    def stats(self) -> Dict:
        total = self.passed + self.rejected
        return {"passed": self.passed, "rejected": self.rejected,
                "pass_rate": round(self.passed/total*100, 1) if total else 0}

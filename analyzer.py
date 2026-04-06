import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Issue:
    line: int
    column: int
    severity: str          # "error" | "warning" | "info"
    code: str              # e.g. "BP001"
    message: str
    suggestion: str = ""

    def to_dict(self):
        return {
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


class StaticAnalyzer:
    """
    Lightweight rule-based static analyzer.
    Supports deep AST analysis for Python, regex-based for others.
    """

    def analyze(self, code: str, language: str = "python") -> Dict[str, Any]:
        issues: List[Issue] = []

        if language.lower() == "python":
            issues.extend(self._analyze_python(code))
        else:
            issues.extend(self._analyze_generic(code, language))

        return {
            "issues": [i.to_dict() for i in issues],
            "total": len(issues),
            "breakdown": self._breakdown(issues),
        }

    # ------------------------------------------------------------------ #
    #  Python AST analysis
    # ------------------------------------------------------------------ #

    def _analyze_python(self, code: str) -> List[Issue]:
        issues: List[Issue] = []

        # Syntax check first
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append(Issue(
                line=e.lineno or 0,
                column=e.offset or 0,
                severity="error",
                code="BP000",
                message=f"Syntax error: {e.msg}",
                suggestion="Fix the syntax error before further analysis.",
            ))
            return issues

        visitor = _PythonASTVisitor()
        visitor.visit(tree)
        issues.extend(visitor.issues)

        # Regex-based checks (things AST misses)
        issues.extend(self._python_regex_checks(code))

        return issues

    def _python_regex_checks(self, code: str) -> List[Issue]:
        issues: List[Issue] = []
        lines = code.splitlines()

        patterns = [
            (r'\beval\s*\(', "BP020", "warning",
             "Use of eval() is dangerous", "Avoid eval(); use safer alternatives."),
            (r'\bexec\s*\(', "BP021", "warning",
             "Use of exec() is dangerous", "Avoid exec(); refactor logic instead."),
            (r'password\s*=\s*["\'][^"\']+["\']', "BP022", "error",
             "Hardcoded password detected", "Use environment variables or a secrets manager."),
            (r'secret\s*=\s*["\'][^"\']+["\']', "BP023", "error",
             "Hardcoded secret detected", "Use environment variables or a secrets manager."),
            (r'\bprint\s*\(', "BP024", "info",
             "Debug print() statement found", "Remove or replace with proper logging."),
            (r'TODO|FIXME|HACK|XXX', "BP025", "info",
             "Unresolved TODO/FIXME comment", "Address or track this in your issue tracker."),
            (r'time\.sleep\s*\(\s*\d{2,}', "BP026", "warning",
             "Long sleep() call detected", "Consider async patterns or event-driven design."),
        ]

        for i, line in enumerate(lines, start=1):
            for pattern, code_id, severity, message, suggestion in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    col = (re.search(pattern, line, re.IGNORECASE).start() + 1)
                    issues.append(Issue(
                        line=i, column=col,
                        severity=severity, code=code_id,
                        message=message, suggestion=suggestion,
                    ))

        return issues

    # ------------------------------------------------------------------ #
    #  Generic (non-Python) regex analysis
    # ------------------------------------------------------------------ #

    def _analyze_generic(self, code: str, language: str) -> List[Issue]:
        issues: List[Issue] = []
        lines = code.splitlines()

        common_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "BP022", "error",
             "Hardcoded password detected", "Use environment variables."),
            (r'secret\s*=\s*["\'][^"\']+["\']', "BP023", "error",
             "Hardcoded secret detected", "Use environment variables."),
            (r'TODO|FIXME|HACK', "BP025", "info",
             "Unresolved TODO/FIXME comment", "Address or track this."),
            (r'console\.log\s*\(', "BP030", "info",
             "Debug console.log() found", "Remove before production."),
            (r'debugger;', "BP031", "warning",
             "Debugger statement found", "Remove debugger statements."),
            (r'innerHTML\s*=', "BP032", "warning",
             "Direct innerHTML assignment — possible XSS", "Use textContent or sanitize input."),
            (r'eval\s*\(', "BP020", "warning",
             "Use of eval() is dangerous", "Avoid eval(); refactor."),
        ]

        for i, line in enumerate(lines, start=1):
            for pattern, code_id, severity, message, suggestion in common_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    col = (re.search(pattern, line, re.IGNORECASE).start() + 1)
                    issues.append(Issue(
                        line=i, column=col,
                        severity=severity, code=code_id,
                        message=message, suggestion=suggestion,
                    ))

        return issues

    def _breakdown(self, issues: List[Issue]) -> Dict[str, int]:
        breakdown = {"error": 0, "warning": 0, "info": 0}
        for issue in issues:
            breakdown[issue.severity] = breakdown.get(issue.severity, 0) + 1
        return breakdown


# ------------------------------------------------------------------ #
#  AST Visitor — Python-specific rules
# ------------------------------------------------------------------ #

class _PythonASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.issues: List[Issue] = []
        self._function_stack: List[ast.FunctionDef] = []

    # --- Bare except ---
    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self.issues.append(Issue(
                line=node.lineno, column=node.col_offset,
                severity="warning", code="BP001",
                message="Bare 'except:' clause catches all exceptions",
                suggestion="Catch specific exception types (e.g., except ValueError:).",
            ))
        self.generic_visit(node)

    # --- Mutable default arguments ---
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._function_stack.append(node)
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.issues.append(Issue(
                    line=node.lineno, column=node.col_offset,
                    severity="warning", code="BP002",
                    message=f"Mutable default argument in '{node.name}'",
                    suggestion="Use None as default and initialise inside the function.",
                ))
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    # --- Comparison to None with == ---
    def visit_Compare(self, node: ast.Compare):
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comparator, ast.Constant) and comparator.value is None:
                self.issues.append(Issue(
                    line=node.lineno, column=node.col_offset,
                    severity="warning", code="BP003",
                    message="Use 'is None' / 'is not None' instead of '== None'",
                    suggestion="Replace '== None' with 'is None'.",
                ))
        self.generic_visit(node)

    # --- Unused variables (simple heuristic: assigned but never loaded) ---
    def visit_Module(self, node: ast.Module):
        self._check_unused_vars(node)
        self.generic_visit(node)

    def _check_unused_vars(self, tree):
        assigned = {}
        loaded = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    assigned[node.id] = node
                elif isinstance(node.ctx, ast.Load):
                    loaded.add(node.id)

        for name, node in assigned.items():
            if name not in loaded and not name.startswith("_"):
                self.issues.append(Issue(
                    line=node.lineno, column=node.col_offset,
                    severity="info", code="BP004",
                    message=f"Variable '{name}' assigned but never used",
                    suggestion=f"Remove '{name}' or prefix with '_' if intentionally unused.",
                ))

    # --- Division by zero (literal) ---
    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.issues.append(Issue(
                    line=node.lineno, column=node.col_offset,
                    severity="error", code="BP005",
                    message="Division by zero detected",
                    suggestion="Ensure the divisor is never zero before dividing.",
                ))
        self.generic_visit(node)

    # --- Assert in production code ---
    def visit_Assert(self, node: ast.Assert):
        self.issues.append(Issue(
            line=node.lineno, column=node.col_offset,
            severity="info", code="BP006",
            message="Assert statement found — disabled with -O flag",
            suggestion="Use explicit if/raise checks for production validation.",
        ))
        self.generic_visit(node)

    # --- Global variable usage ---
    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.issues.append(Issue(
                line=node.lineno, column=node.col_offset,
                severity="warning", code="BP007",
                message=f"Use of 'global {name}' detected",
                suggestion="Avoid global state; pass values explicitly or use classes.",
            ))
        self.generic_visit(node)

    # --- Empty except pass ---
    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            if (len(handler.body) == 1 and
                    isinstance(handler.body[0], ast.Pass)):
                self.issues.append(Issue(
                    line=handler.lineno, column=handler.col_offset,
                    severity="warning", code="BP008",
                    message="Silent exception handler (except: pass)",
                    suggestion="Log or re-raise the exception instead of silently ignoring it.",
                ))
        self.generic_visit(node)

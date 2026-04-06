import ast
import re
import math
from typing import Dict, Any


class FeatureExtractor:
    """
    Converts raw source code into a fixed-length numeric feature vector.
    Works for Python (deep AST) and other languages (surface metrics).

    Feature groups:
        1. Surface metrics       (lines, length, density)
        2. AST structural        (functions, classes, loops, conditions)
        3. Complexity            (cyclomatic, nesting depth, Halstead proxies)
        4. Code smell signals    (magic numbers, long lines, deep nesting)
        5. Static issue counts   (from StaticAnalyzer)
    """

    FEATURE_NAMES = [
        # --- Surface ---
        "loc",                    # lines of code (non-blank)
        "blank_ratio",            # blank lines / total lines
        "comment_ratio",          # comment lines / total lines
        "avg_line_length",        # average characters per line
        "max_line_length",        # longest line
        "char_count",             # total characters

        # --- AST structural ---
        "num_functions",
        "num_classes",
        "num_imports",
        "num_loops",              # for + while
        "num_conditions",         # if/elif
        "num_try_except",
        "num_return_stmts",
        "num_assignments",
        "num_comparisons",
        "num_boolean_ops",
        "num_lambda",
        "num_list_comp",
        "num_dict_comp",
        "num_yield",
        "num_raise",
        "num_assert",
        "num_global",
        "num_nonlocal",
        "num_delete",

        # --- Complexity ---
        "cyclomatic_complexity",  # approximation via decision points
        "max_nesting_depth",
        "avg_params_per_func",
        "max_params_per_func",
        "halstead_vocab",         # unique operators + operands
        "halstead_length",        # total operators + operands

        # --- Code smell signals ---
        "has_bare_except",        # 0/1
        "has_mutable_defaults",   # 0/1
        "has_eval_exec",          # 0/1
        "has_hardcoded_secret",   # 0/1
        "has_debug_prints",       # 0/1
        "has_todo_fixme",         # 0/1
        "has_global_usage",       # 0/1
        "magic_number_count",
        "long_function_count",    # functions > 50 lines
        "long_line_count",        # lines > 100 chars

        # --- Static issue counts ---
        "static_errors",
        "static_warnings",
        "static_infos",
        "static_total",
    ]

    N_FEATURES = len(FEATURE_NAMES)

    def extract(self, code: str, language: str = "python", static_results: Dict = None) -> list:
        """
        Returns a list of N_FEATURES floats.
        """
        features = {}

        # Surface metrics (language-agnostic)
        features.update(self._surface_metrics(code))

        # Structural + complexity (Python: AST; others: regex)
        if language.lower() == "python":
            features.update(self._python_ast_features(code))
        else:
            features.update(self._generic_features(code))

        # Code smell signals
        features.update(self._smell_signals(code, language))

        # Static analysis counts
        features.update(self._static_counts(static_results))

        # Return in canonical order
        return [float(features.get(name, 0.0)) for name in self.FEATURE_NAMES]

    # ------------------------------------------------------------------ #

    def _surface_metrics(self, code: str) -> Dict:
        lines = code.splitlines()
        total = max(len(lines), 1)

        blank = sum(1 for l in lines if not l.strip())
        comments = sum(1 for l in lines if l.strip().startswith(("#", "//", "/*", "*", "--")))
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith(("#", "//"))]
        loc = max(len(code_lines), 1)
        lengths = [len(l) for l in lines]

        return {
            "loc": loc,
            "blank_ratio": blank / total,
            "comment_ratio": comments / total,
            "avg_line_length": sum(lengths) / total,
            "max_line_length": max(lengths) if lengths else 0,
            "char_count": len(code),
        }

    def _python_ast_features(self, code: str) -> Dict:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return self._generic_features(code)

        v = _ASTFeatureVisitor()
        v.visit(tree)

        avg_params = (
            sum(v.param_counts) / len(v.param_counts) if v.param_counts else 0
        )
        max_params = max(v.param_counts) if v.param_counts else 0

        # Halstead proxies
        operators = set()
        operands = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                operators.add(type(node.op).__name__)
            if isinstance(node, ast.Name):
                operands.add(node.id)
            if isinstance(node, ast.Constant):
                operands.add(str(node.value))

        return {
            "num_functions": v.num_functions,
            "num_classes": v.num_classes,
            "num_imports": v.num_imports,
            "num_loops": v.num_loops,
            "num_conditions": v.num_conditions,
            "num_try_except": v.num_try_except,
            "num_return_stmts": v.num_return_stmts,
            "num_assignments": v.num_assignments,
            "num_comparisons": v.num_comparisons,
            "num_boolean_ops": v.num_boolean_ops,
            "num_lambda": v.num_lambda,
            "num_list_comp": v.num_list_comp,
            "num_dict_comp": v.num_dict_comp,
            "num_yield": v.num_yield,
            "num_raise": v.num_raise,
            "num_assert": v.num_assert,
            "num_global": v.num_global,
            "num_nonlocal": v.num_nonlocal,
            "num_delete": v.num_delete,
            "cyclomatic_complexity": 1 + v.num_conditions + v.num_loops + v.num_try_except,
            "max_nesting_depth": v.max_depth,
            "avg_params_per_func": avg_params,
            "max_params_per_func": max_params,
            "halstead_vocab": len(operators) + len(operands),
            "halstead_length": v.total_operators + v.total_operands,
            "long_function_count": v.long_function_count,
        }

    def _generic_features(self, code: str) -> Dict:
        """Regex-based fallback for non-Python code."""
        return {
            "num_functions": len(re.findall(r'\bfunction\b|\bdef\b|\bfunc\b|\bvoid\b\s+\w+\s*\(', code)),
            "num_classes": len(re.findall(r'\bclass\b', code)),
            "num_imports": len(re.findall(r'\bimport\b|\brequire\b|\binclude\b', code)),
            "num_loops": len(re.findall(r'\bfor\b|\bwhile\b|\bforeach\b', code)),
            "num_conditions": len(re.findall(r'\bif\b|\belif\b|\belse if\b|\bswitch\b', code)),
            "num_try_except": len(re.findall(r'\btry\b|\bcatch\b|\bexcept\b', code)),
            "num_return_stmts": len(re.findall(r'\breturn\b', code)),
            "num_assignments": len(re.findall(r'(?<![=!<>])=(?!=)', code)),
            "num_comparisons": len(re.findall(r'==|!=|<=|>=|<|>', code)),
            "num_boolean_ops": len(re.findall(r'\band\b|\bor\b|\bnot\b|&&|\|\|', code)),
            "num_lambda": len(re.findall(r'\blambda\b|=>', code)),
            "num_list_comp": 0,
            "num_dict_comp": 0,
            "num_yield": len(re.findall(r'\byield\b', code)),
            "num_raise": len(re.findall(r'\bthrow\b|\braise\b', code)),
            "num_assert": len(re.findall(r'\bassert\b', code)),
            "num_global": len(re.findall(r'\bglobal\b', code)),
            "num_nonlocal": 0,
            "num_delete": len(re.findall(r'\bdelete\b|\bdel\b', code)),
            "cyclomatic_complexity": 1 + len(re.findall(r'\bif\b|\bfor\b|\bwhile\b|\bcatch\b', code)),
            "max_nesting_depth": self._estimate_nesting(code),
            "avg_params_per_func": 0,
            "max_params_per_func": 0,
            "halstead_vocab": len(set(re.findall(r'\w+', code))),
            "halstead_length": len(re.findall(r'\w+', code)),
            "long_function_count": 0,
        }

    def _smell_signals(self, code: str, language: str) -> Dict:
        lines = code.splitlines()
        magic_numbers = len(re.findall(r'(?<!\w)(?<!\.)\d{2,}(?!\w)(?!\.)', code))

        return {
            "has_bare_except": int(bool(re.search(r'\bexcept\s*:', code))),
            "has_mutable_defaults": int(bool(re.search(r'def\s+\w+\s*\([^)]*=\s*[\[\{]', code))),
            "has_eval_exec": int(bool(re.search(r'\beval\s*\(|\bexec\s*\(', code))),
            "has_hardcoded_secret": int(bool(re.search(
                r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']', code, re.IGNORECASE))),
            "has_debug_prints": int(bool(re.search(r'\bprint\s*\(|\bconsole\.log\s*\(', code))),
            "has_todo_fixme": int(bool(re.search(r'TODO|FIXME|HACK|XXX', code))),
            "has_global_usage": int(bool(re.search(r'\bglobal\s+\w', code))),
            "magic_number_count": magic_numbers,
            "long_line_count": sum(1 for l in lines if len(l) > 100),
        }

    def _static_counts(self, static_results: Dict) -> Dict:
        if not static_results:
            return {"static_errors": 0, "static_warnings": 0, "static_infos": 0, "static_total": 0}
        bd = static_results.get("breakdown", {})
        total = static_results.get("total", 0)
        return {
            "static_errors": bd.get("error", 0),
            "static_warnings": bd.get("warning", 0),
            "static_infos": bd.get("info", 0),
            "static_total": total,
        }

    def _estimate_nesting(self, code: str) -> int:
        depth = max_depth = 0
        for ch in code:
            if ch in "({[":
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch in ")}]":
                depth = max(0, depth - 1)
        return max_depth


# ------------------------------------------------------------------ #

class _ASTFeatureVisitor(ast.NodeVisitor):
    def __init__(self):
        self.num_functions = 0
        self.num_classes = 0
        self.num_imports = 0
        self.num_loops = 0
        self.num_conditions = 0
        self.num_try_except = 0
        self.num_return_stmts = 0
        self.num_assignments = 0
        self.num_comparisons = 0
        self.num_boolean_ops = 0
        self.num_lambda = 0
        self.num_list_comp = 0
        self.num_dict_comp = 0
        self.num_yield = 0
        self.num_raise = 0
        self.num_assert = 0
        self.num_global = 0
        self.num_nonlocal = 0
        self.num_delete = 0
        self.param_counts = []
        self.max_depth = 0
        self.long_function_count = 0
        self.total_operators = 0
        self.total_operands = 0
        self._depth = 0

    def _enter(self):
        self._depth += 1
        self.max_depth = max(self.max_depth, self._depth)

    def _exit(self):
        self._depth -= 1

    def visit_FunctionDef(self, node):
        self.num_functions += 1
        self.param_counts.append(len(node.args.args))
        func_lines = (node.end_lineno or node.lineno) - node.lineno
        if func_lines > 50:
            self.long_function_count += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.num_classes += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_Import(self, node):      self.num_imports += 1;      self.generic_visit(node)
    def visit_ImportFrom(self, node):  self.num_imports += 1;      self.generic_visit(node)
    def visit_For(self, node):         self.num_loops += 1;        self._enter(); self.generic_visit(node); self._exit()
    def visit_While(self, node):       self.num_loops += 1;        self._enter(); self.generic_visit(node); self._exit()
    def visit_If(self, node):          self.num_conditions += 1;   self._enter(); self.generic_visit(node); self._exit()
    def visit_Try(self, node):         self.num_try_except += 1;   self.generic_visit(node)
    def visit_Return(self, node):      self.num_return_stmts += 1; self.generic_visit(node)
    def visit_Assign(self, node):      self.num_assignments += 1;  self.generic_visit(node)
    def visit_AugAssign(self, node):   self.num_assignments += 1;  self.generic_visit(node)
    def visit_Compare(self, node):     self.num_comparisons += 1;  self.generic_visit(node)
    def visit_BoolOp(self, node):      self.num_boolean_ops += 1;  self.generic_visit(node)
    def visit_Lambda(self, node):      self.num_lambda += 1;       self.generic_visit(node)
    def visit_ListComp(self, node):    self.num_list_comp += 1;    self.generic_visit(node)
    def visit_DictComp(self, node):    self.num_dict_comp += 1;    self.generic_visit(node)
    def visit_Yield(self, node):       self.num_yield += 1;        self.generic_visit(node)
    def visit_YieldFrom(self, node):   self.num_yield += 1;        self.generic_visit(node)
    def visit_Raise(self, node):       self.num_raise += 1;        self.generic_visit(node)
    def visit_Assert(self, node):      self.num_assert += 1;       self.generic_visit(node)
    def visit_Global(self, node):      self.num_global += 1;       self.generic_visit(node)
    def visit_Nonlocal(self, node):    self.num_nonlocal += 1;     self.generic_visit(node)
    def visit_Delete(self, node):      self.num_delete += 1;       self.generic_visit(node)

    def visit_BinOp(self, node):
        self.total_operators += 1
        self.generic_visit(node)

    def visit_Name(self, node):
        self.total_operands += 1
        self.generic_visit(node)

    def visit_Constant(self, node):
        self.total_operands += 1
        self.generic_visit(node)

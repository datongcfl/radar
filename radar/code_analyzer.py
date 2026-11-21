"""Conservative, stdlib-only Python source relationship analysis.

Finds explicit import dependencies and narrowly patterned status transitions.
Every result is a static candidate with exact source locations, never runtime proof.
"""
from __future__ import annotations

import ast
from typing import Any


def _target_key(node: ast.AST) -> str:
    # Ignore Load/Store contexts so the same attribute compares equal on both sides.
    if isinstance(node, ast.Attribute):
        parent = _target_key(node.value)
        return parent + "." + node.attr if parent else ""
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _status_guard(node: ast.AST) -> tuple[str, str] | None:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    if not isinstance(node.ops[0], (ast.Eq, ast.Is)):
        return None
    left, right = node.left, node.comparators[0]
    if isinstance(right, ast.Constant) and isinstance(right.value, str):
        target, value = left, right.value
    elif isinstance(left, ast.Constant) and isinstance(left.value, str):
        target, value = right, left.value
    else:
        return None
    if not (isinstance(target, ast.Attribute) and target.attr.lower() in ("status", "state", "docstatus")
            or isinstance(target, ast.Name) and target.id.lower() in ("status", "state", "docstatus")):
        return None
    key = _target_key(target)
    return (key, value) if key else None


def _assigned_status(target: ast.AST) -> tuple[str, str] | None:
    if isinstance(target, (ast.Tuple, ast.List)):
        return None
    if isinstance(target, ast.Attribute) and target.attr.lower() in ("status", "state", "docstatus"):
        return _target_key(target), ""
    if isinstance(target, ast.Name) and target.id.lower() in ("status", "state", "docstatus"):
        return _target_key(target), ""
    return None


class _StateVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.guards: list[tuple[str, str, int]] = []
        self.transitions: list[dict[str, Any]] = []
        self.scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append("class:" + node.name)
        for item in node.body:
            self.visit(item)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append("function:" + node.name)
        for item in node.body:
            self.visit(item)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If) -> None:
        guard = _status_guard(node.test)
        if guard:
            self.guards.append((guard[0], guard[1], node.lineno))
        for item in node.body:
            self.visit(item)
        if guard:
            self.guards.pop()
        for item in node.orelse:
            self.visit(item)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                assigned = _assigned_status(target)
                if not assigned:
                    continue
                for key, from_state, guard_line in reversed(self.guards):
                    if key == assigned[0] and from_state != node.value.value:
                        self.transitions.append({
                            "from_state": from_state,
                            "to_state": node.value.value,
                            "guard_line": guard_line,
                            "assignment_line": node.lineno,
                            "scope": list(self.scope),
                            "target": key,
                        })
                        break
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            assigned = _assigned_status(node.target)
            if assigned:
                for key, from_state, guard_line in reversed(self.guards):
                    if key == assigned[0] and from_state != node.value.value:
                        self.transitions.append({
                            "from_state": from_state,
                            "to_state": node.value.value,
                            "guard_line": guard_line,
                            "assignment_line": node.lineno,
                            "scope": list(self.scope),
                            "target": key,
                        })
                        break
        self.generic_visit(node)


def analyze_python_source(content: str, path: str = "") -> dict[str, Any]:
    """Return import references and explicit guarded status assignments."""
    try:
        tree = ast.parse(content, filename=path or "<source>")
    except (SyntaxError, ValueError, TypeError) as exc:
        return {"status": "parse_failed", "reason": str(exc)[:240],
                "imports": [], "state_transitions": []}

    imports: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "line": node.lineno, "kind": "import"})
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append({"module": node.module, "line": node.lineno,
                                "kind": "from_import",
                                "names": [alias.name for alias in node.names]})
    visitor = _StateVisitor()
    visitor.visit(tree)
    imports.sort(key=lambda item: (item["line"], item["module"], item["kind"]))
    transitions = sorted(visitor.transitions,
                         key=lambda item: (item["assignment_line"], item["from_state"], item["to_state"]))
    return {"status": "parsed", "imports": imports, "state_transitions": transitions}

from __future__ import annotations

import ast
from pathlib import Path


def ownership_errors(source: str, path: str) -> list[str]:
    """Find concrete plugin imports or type dispatch outside plugin ownership."""
    if "/node/plugins/" in ("/" + path.replace("\\", "/")) or path.endswith(
        "node/registry.py"
    ):
        return []
    errors = []
    for item in ast.walk(ast.parse(source)):
        if (
            isinstance(item, ast.ImportFrom)
            and item.module
            and (
                "node.plugins" in item.module
                or item.module.startswith("plugins.")
                or (
                    item.module == "node"
                    and any(alias.name == "plugins" for alias in item.names)
                )
            )
        ):
            errors.append(f"{path}:{item.lineno}: concrete plugin import")
        if isinstance(item, ast.Import) and any(
            "node.plugins" in alias.name for alias in item.names
        ):
            errors.append(f"{path}:{item.lineno}: concrete plugin module import")
        if isinstance(item, ast.MatchClass) and isinstance(item.cls, ast.Name):
            if item.cls.id.endswith("Node") and item.cls.id != "NodeBase":
                errors.append(f"{path}:{item.lineno}: concrete node match dispatch")
        if isinstance(item, ast.Compare) and any(
            isinstance(n, ast.Attribute) and n.attr == "kind" for n in ast.walk(item)
        ):
            if any(
                isinstance(n, ast.Constant) and isinstance(n.value, str)
                for n in ast.walk(item)
            ):
                errors.append(f"{path}:{item.lineno}: kind dispatch")
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == "isinstance"
        ):
            types = item.args[1:] if len(item.args) > 1 else []
            if any(
                isinstance(n, ast.Name) and n.id.endswith("Node") and n.id != "NodeBase"
                for t in types
                for n in ast.walk(t)
            ):
                errors.append(f"{path}:{item.lineno}: concrete node type dispatch")
    return errors


def check(root: Path) -> list[str]:
    """Check every production Python module outside the plugin catalog."""
    errors = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if relative.parts[0] in {"tools", "tests"} or any(
            part.startswith(".") for part in relative.parts
        ):
            continue
        errors.extend(
            ownership_errors(path.read_text(encoding="utf-8-sig"), relative.as_posix())
        )
    return errors


def self_test() -> None:
    """Require the checker to accept hook dispatch and reject concrete dispatch."""
    assert not ownership_errors("node.add_constraints(builder)", "model/solver.py")
    mutant = "from node.plugins.div import DivNode\nif isinstance(node, DivNode):\n    pass\n"
    assert len(ownership_errors(mutant, "model/solver.py")) == 2
    assert not ownership_errors(mutant, "node/plugins/div_div.py")
    assert ownership_errors('if node.kind == "div": pass', "model/graph.py")
    assert ownership_errors("import node.plugins.div as divider", "model/graph.py")
    assert ownership_errors("from .plugins.div import DivNode", "model/graph.py")
    assert ownership_errors("match node:\n    case DivNode(): pass", "model/graph.py")


if __name__ == "__main__":
    self_test()
    problems = check(Path(__file__).resolve().parents[1])
    if problems:
        raise SystemExit("\n".join(problems))
    print("PASS plugin ownership and checker mutants")

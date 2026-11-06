from __future__ import annotations

import ast
import json
from pathlib import Path


def ownership_errors(source: str, path: str, private_fields=()) -> list[str]:
    """Reject static leaf imports and private-field use, including in registry."""
    relative = Path(path)
    leaf = relative.parent.as_posix() == "node/plugins"
    package = list(relative.parent.parts)
    errors = []
    for item in ast.walk(ast.parse(source)):
        targets = []
        if isinstance(item, ast.ImportFrom):
            base = package[: len(package) - item.level + 1] if item.level else []
            module = ".".join([*base, *(item.module or "").split(".")]).strip(".")
            targets = [module, *(module + "." + alias.name for alias in item.names)]
        elif isinstance(item, ast.Import):
            targets = [alias.name for alias in item.names]
        if any(
            target.startswith("node.plugins.")
            and target != ".".join((*package, relative.stem))
            for target in targets
        ):
            errors.append(f"{path}:{item.lineno}: concrete plugin import")
        if not leaf and isinstance(item, ast.Attribute) and item.attr in private_fields:
            errors.append(f"{path}:{item.lineno}: plugin-private attribute {item.attr}")
        if not leaf and isinstance(item, ast.Compare):
            if any(
                isinstance(n, ast.Attribute) and n.attr == "kind"
                for n in ast.walk(item)
            ):
                if any(
                    isinstance(n, ast.Constant) and isinstance(n.value, str)
                    for n in (item.left, *item.comparators)
                ):
                    errors.append(f"{path}:{item.lineno}: concrete kind dispatch")
    return errors


def check(root: Path) -> list[str]:
    sources = {
        path: path.read_text(encoding="utf-8-sig")
        for path in root.rglob("*.py")
        if not any(
            part.startswith(".") or part in {"tools", "tests", "__pycache__"}
            for part in path.relative_to(root).parts
        )
    }
    errors = []
    private = set()
    trees = {path: ast.parse(source) for path, source in sources.items()}
    references = {
        item.id
        for tree in trees.values()
        for item in ast.walk(tree)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }
    references.update(
        item.attr
        for tree in trees.values()
        for item in ast.walk(tree)
        if isinstance(item, ast.Attribute)
    )
    for path, source in sources.items():
        if path.parent != root / "node/plugins" or path.name == "__init__.py":
            continue
        kinds = []
        for cls in (n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)):
            for field in cls.body:
                if not isinstance(field, ast.AnnAssign) or not isinstance(
                    field.target, ast.Name
                ):
                    continue
                if field.target.id.endswith("_kind"):
                    private.add(field.target.id)
                if field.target.id == "kind" and isinstance(field.value, ast.Constant):
                    kinds.append(field.value.value)
        if kinds != [path.stem]:
            errors.append(
                f"{path.relative_to(root)}: exactly one owned kind must match filename"
            )
    for path, source in sources.items():
        errors.extend(
            ownership_errors(source, path.relative_to(root).as_posix(), private)
        )
        for item in trees[path].body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name.startswith("_")
                and item.name not in references
            ):
                errors.append(
                    f"{path.relative_to(root)}:{item.lineno}: unreferenced private function {item.name}"
                )
    for path in root.rglob("*.j2"):
        source = path.read_text(encoding="utf-8")
        for field in private:
            if "." + field in source:
                errors.append(
                    f"{path.relative_to(root)}: plugin-private template attribute {field}"
                )
    return errors


def self_test() -> None:
    assert not ownership_errors("node.add_constraints(builder)", "model/solver.py")
    assert ownership_errors("from node.plugins.probe import Probe", "node/registry.py")
    assert ownership_errors("from .probe import Probe", "node/plugins/other.py")
    assert not ownership_errors(
        "from node.behaviors import TransparentNode", "node/plugins/probe.py"
    )
    assert ownership_errors("node.device_kind", "registers/plan.py", ("device_kind",))
    assert ownership_errors('if node.kind == "probe": pass', "model/graph.py")


if __name__ == "__main__":
    self_test()
    problems = check(Path(__file__).resolve().parents[1])
    print(
        json.dumps(
            {
                "pass": not problems,
                "scope": "static file ownership, imports, selectors, templates and private-call references",
                "errors": problems,
            },
            indent=2,
        )
    )
    raise SystemExit(bool(problems))

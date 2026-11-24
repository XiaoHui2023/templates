from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def leaf_names(root: Path) -> set[str]:
    """Return concrete node names from the explicit SV plugin files."""
    return {path.stem.removesuffix(".sv") for path in (root / "node" / "plugin").glob("*.sv.j2")}


def python_leaf_names(root: Path) -> set[str]:
    """Return Python plugin stems, excluding package and shared-family modules."""
    directory = root / "node" / "python" / "plugins"
    return {
        path.stem
        for path in directory.glob("*.py")
        if not path.stem.startswith("_")
    }


def generic_sources(root: Path) -> list[Path]:
    """Return sources that must remain independent of concrete node names."""
    paths: list[Path] = []
    for directory in (
        root / "node" / "base",
        root / "node" / "plugin" / "support",
        root / "component",
        root / "sequence",
        root / "top",
    ):
        if directory.exists():
            paths.extend(directory.rglob("*.sv.j2"))
    for path in (
        root / "models.py",
        root / "reg_paths.py",
        root / "schema_error.py",
        root / "node" / "python" / "base.py",
        root / "node" / "python" / "config.py",
    ):
        if path.exists():
            paths.append(path)
    return paths


def without_runtime_queue_casts(text: str) -> str:
    def strip_cast(task: re.Match[str]) -> str:
        body = task[0]
        for name in re.findall(r"\buvm_queue\s*#\(\s*(?:time|int)\s*\)\s+(\w+)\s*;", body):
            body = re.sub(
                rf"\$cast\s*\(\s*{re.escape(name)}\s*,\s*context_h\.runtime_state\(this\)\s*\)",
                "",
                body,
            )
        return body

    return re.sub(r"\btask\b[^;]*;(?:(?!\btask\b).)*?\bendtask\b", strip_cast, text, flags=re.S)


def violations(root: Path = ROOT) -> list[str]:
    """Find centralized dispatch or concrete node ownership outside leaf plugins."""
    failures: list[str] = []
    names = leaf_names(root)
    python_names = python_leaf_names(root)
    literal_names = names - {"source"}
    forbidden = (
        r"\$cast\s*\(",
        r"\bkind\s*(?:==|!=)",
        r"\bcase\s*\(\s*kind\s*\)",
        r"\bplugin_configuration\b",
        r"\bnode_cfg::",
        r"\bconfig_reg_pll_node\b",
        r"\bpll_cfg\b",
    )
    for path in generic_sources(root):
        text = path.read_text(encoding="utf-8")
        dispatch_text = without_runtime_queue_casts(text)
        for pattern in forbidden:
            if re.search(pattern, dispatch_text):
                failures.append(f"{path.relative_to(root)}: forbidden centralized dispatch {pattern}")
        for name in literal_names:
            if re.search(rf'(?<![A-Za-z0-9_$])["\']{re.escape(name)}["\']', text):
                failures.append(f"{path.relative_to(root)}: concrete node {name!r} escaped its plugin")

    for name in names:
        owners = [
            path for path in (root / "node" / "plugin").glob("*.sv.j2")
            if f'kind = "{name}"' in path.read_text(encoding="utf-8")
        ]
        if len(owners) != 1:
            failures.append(f"node {name!r}: expected one leaf kind owner, found {len(owners)}")
    for name in sorted(names - python_names):
        failures.append(f"node {name!r}: missing node/python/plugins/{name}.py")
    for name in sorted(python_names - names):
        failures.append(f"node/python/plugins/{name}.py: missing SV leaf plugin")
    return failures


def self_test() -> int:
    """Prove generic leakage fails while a leaf implementation is accepted."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        leaf = root / "node" / "plugin" / "gate.sv.j2"
        leaf.parent.mkdir(parents=True)
        leaf.write_text('class gate; function new(); kind = "gate"; endfunction endclass\n', encoding="utf-8")
        if not violations(root):
            print("missing Python-plugin mutant was accepted")
            return 1
        python_leaf = root / "node" / "python" / "plugins" / "gate.py"
        python_leaf.parent.mkdir(parents=True)
        python_leaf.write_text("class GateConfig: pass\n", encoding="utf-8")
        if violations(root):
            print("matching plugin pair was rejected")
            return 1
        support = root / "node" / "plugin" / "support" / "bad.sv.j2"
        support.parent.mkdir(parents=True)
        support.write_text(
            "task poll(); uvm_queue#(time) state; if (!$cast(state, context_h.runtime_state(this))) ; endtask\n",
            encoding="utf-8",
        )
        if violations(root):
            print("generic runtime queue cast was rejected")
            return 1
        with support.open("a", encoding="utf-8") as stream:
            stream.write(
                "task bad(); gate state; if ($cast(state, context_h.runtime_state(this))) ; endtask\n"
            )
        if not violations(root):
            print("SV support mutant was accepted")
            return 1
        support.unlink()
        core = root / "models.py"
        core.write_text('if node.kind == "gate":\n    pass\n', encoding="utf-8")
        if not violations(root):
            print("Python core mutant was accepted")
            return 1
        core.unlink()
        if violations(root):
            print("leaf-plugin implementation was rejected")
            return 1
    print("plugin ownership self-test passed")
    return 0


def main() -> int:
    """Run the production scan or its fault-injection proof."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    failures = violations()
    if failures:
        print("plugin ownership check failed:")
        print("\n".join(failures))
        return 1
    print("plugin ownership check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

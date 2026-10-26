"""Reject centralized concrete-node dispatch in the clock-tree template layer."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "node" / "plugin"
CORE_DIRS = (ROOT / "node" / "base", ROOT / "tree", ROOT / "component", ROOT / "sequence", ROOT / "top")


def violations(root: Path = ROOT) -> list[str]:
    plugin = root / "node" / "plugin"
    support = plugin / "support"
    paths = [*support.rglob("*.sv.j2")]
    for directory in (root / "node" / "base", root / "tree", root / "component", root / "sequence", root / "top"):
        if directory.exists():
            paths.extend(directory.rglob("*.sv.j2"))

    failures: list[str] = []
    forbidden = ("$cast(", "plugin_configuration", "node_cfg::", "config_reg_pll_node")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                failures.append(f"{path.relative_to(root)}: forbidden centralized dispatch token {token}")
    return failures


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        bad = root / "node" / "plugin" / "support" / "bad.sv.j2"
        bad.parent.mkdir(parents=True)
        bad.write_text("if ($cast(some_node, node_h)) ;\n", encoding="utf-8")
        if not violations(root):
            print("ownership mutant was accepted")
            return 1
        good = root / "node" / "plugin" / "gate.sv.j2"
        good.parent.mkdir(parents=True, exist_ok=True)
        good.write_text("if ($cast(some_node, node_h)) ;\n", encoding="utf-8")
        bad.unlink()
        if violations(root):
            print("leaf-plugin implementation was rejected")
            return 1
    print("plugin ownership self-test passed")
    return 0


def main() -> int:
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

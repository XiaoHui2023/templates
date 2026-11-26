"""Verify that the optional config entry leaves the full clock tree unchanged."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

from check_template_pruning import ROOT, renderer


FAMILY = "src/sv/agent/clock_tree"
CONFIG_OUTPUTS = {"config.f", "config.md"}
CONFIG_EXCLUSIONS = {"node/base/test_api.sv", "node/base/reg_snapshot.sv"}


def read_output(output: Path) -> dict[str, str]:
    return {file.relative_to(output).as_posix(): file.read_text(encoding="utf-8")
            for file in output.rglob("*") if file.is_file()}


def filelist(products: dict[str, str], name: str) -> list[str]:
    entries = products.get(name, "").splitlines()
    if not entries or len(entries) != len(set(entries)):
        raise ValueError(f"{name}: empty filelist or repeated entry")
    for entry in entries:
        path = PurePosixPath(entry)
        if (not entry.endswith(".sv") or path.is_absolute() or ".." in path.parts
                or entry != path.as_posix() or entry not in products):
            raise ValueError(f"{name}: invalid entry {entry!r}")
    return entries


def compare(disabled: dict[str, str], enabled: dict[str, str]) -> None:
    if (set(disabled) & CONFIG_OUTPUTS or set(enabled) - set(disabled) != CONFIG_OUTPUTS
            or disabled != {name: text for name, text in enabled.items() if name not in CONFIG_OUTPUTS}):
        raise ValueError("direct_config must add only config.f and config.md")
    all_files = filelist(disabled, "all.f")
    config_files = filelist(enabled, "config.f")
    expected = [name for name in all_files
                if name.startswith("node/") and name not in CONFIG_EXCLUSIONS]
    if config_files != expected or "node/base/config_reg.sv" not in config_files:
        raise ValueError("config.f must load the configuration dependencies in all.f order")
    if "tree.configure();" not in enabled["config.md"]:
        raise ValueError("config.md must show the configuration call")


def check_controls(disabled: dict[str, str], enabled: dict[str, str]) -> int:
    cases = ((disabled | {"config.f": enabled["config.f"]}, enabled),
             (disabled, {name: text for name, text in enabled.items() if name != "config.md"}))
    for off, on in cases:
        try:
            compare(off, on)
        except ValueError:
            continue
        raise ValueError("generation contract accepted an incorrect feature file set")
    return len(cases)


def main() -> None:
    executable = renderer()
    workspace = ROOT / ".agent-tmp"
    workspace.mkdir(exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="clock-tree-generation-", dir=workspace) as directory:
        work = Path(directory)
        for name, enabled in (("normal", False), ("direct_config", True)):
            config = work / f"{name}.json"
            output = work / name
            config.write_text(json.dumps({
                "settings": {"class_regmodel": "regmodel_t", "direct_config": enabled},
                "nodes": {"root": {"kind": "source", "frequence": 24000000},
                          "sink": {"kind": "clk", "source": "root", "path": "dut.clk"}},
            }), encoding="utf-8")
            run = subprocess.run([executable, str(ROOT / FAMILY), str(config), str(output)],
                                 capture_output=True, timeout=25)
            if run.returncode:
                raise ValueError((run.stdout + run.stderr).decode(errors="replace"))
            results[name] = read_output(output)
    disabled, enabled = results["normal"], results["direct_config"]
    compare(disabled, enabled)
    print(json.dumps({"passed": True, "family": FAMILY,
                      "profiles": {name: len(products) for name, products in results.items()},
                      "rejected_controls": check_controls(disabled, enabled)}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Gate the generated scoreboard's feature inventory and report output size."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "src/sv/scoreboard/general"
CORE = ["import.sv", "statistics.sv"]
CHECKER = ["adapter.sv", "entry.sv", "pending.sv"]
BASE = dict(mode="address", checks_enabled=True, callbacks_enabled=True,
            print_payload_enabled=True, atomize=True, match_address=True,
            match_command=False, compare_address=True, compare_command=True,
            compare_data=True, compare_response=False, reuse_read_expectations=False,
            require_golden=True, require_match=True, expected_units=-1,
            check_count=True, check_missing=True, check_unexpected=True, monitor_policy="drop")
PROFILES = {
    "reference": {},
    "off": dict(checks_enabled=False),
    "lean": dict(callbacks_enabled=False, print_payload_enabled=False, compare_data=False,
                 check_count=False, check_missing=False, check_unexpected=False,
                 require_golden=False, require_match=False),
    "address": dict(monitor_policy="buffer", compare_response=True),
    "packet": dict(atomize=False, callbacks_enabled=False, compare_data=False,
                   compare_response=True, match_address=False, monitor_policy="strict"),
    "ordered": dict(mode="ordered", match_command=True, compare_address=False),
    "ordered_address": dict(mode="ordered"),
    "set": dict(mode="set", match_command=True, monitor_policy="strict"),
    "reuse": dict(mode="ordered", reuse_read_expectations=True, monitor_policy="buffer"),
    "state": dict(mode="state", monitor_policy="buffer", expected_units=1),
    "example": dict(mode="state", monitor_policy="buffer"),
}
PROFILES.update({key: {key: False} for key in
                 ("check_count", "check_missing", "check_unexpected", "require_golden", "require_match",
                  "compare_command", "compare_data", "callbacks_enabled", "print_payload_enabled")})


def renderer() -> str:
    """Resolve the project's renderer without changing toolchain state."""
    selected = os.environ.get("JINJA_BUILD_EXECUTABLE")
    local = ROOT / ".codex/toolchain.local.json"
    if selected is None and local.is_file():
        selected = json.loads(local.read_text(encoding="utf-8")).get("jinja_build")
    executable = shutil.which(selected or "jinja-build")
    if not executable:
        raise RuntimeError("Set JINJA_BUILD_EXECUTABLE or configure .codex/toolchain.local.json")
    return executable


def inspect(products: dict[str, str], config: dict) -> tuple[int, int, int]:
    """Require exact files and selected feature witnesses, and reject disabled witnesses."""
    enabled = config["checks_enabled"]
    callback = enabled and config["callbacks_enabled"]
    printing = enabled and config["print_payload_enabled"]
    ordered_files = [*CORE, *(["callback.sv"] if callback else []),
                     *(CHECKER if enabled else []), "scoreboard.sv"]
    if set(products) != {"all.f", *ordered_files} or products["all.f"].splitlines() != ordered_files:
        raise ValueError("unexpected files or compile-list entries")
    if any(not products[name].strip() or re.search(r"\n[ \t]*\n[ \t]*\n", products[name])
           for name in ordered_files):
        raise ValueError("empty or excessively spaced source")
    source = "\n".join(products[name] for name in ordered_files)
    source = re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", source)
    if re.search(r"\bif\s*\(\s*(?:[01]|1'b[01])\s*\)", source):
        raise ValueError("constant runtime branch")
    adapter = products.get("adapter.sv", "")
    equal = adapter.split("::equal(", 1)[-1]
    explicit = config["expected_units"] >= 0
    obligations = {
        "runtime configuration": (False, r"\b(?:uvm_config_db|\w*scoreboard_config|cfg|GP_CONFIG)\b", source),
        "comparison pipeline": (enabled, r"\bcompletion_issues\b", source),
        "bypass accounting": (not enabled, r"\bskipped_packets\b", source),
        "callbacks": (callback, r"\b(?:uvm_register_cb|uvm_callback_iter|GP_CALLBACK|notifying)\b", source),
        "printing": (printing, r"\b(?:print_payload|uvm_default_line_printer|GP_GOLDEN|GP_MONITOR)\b", source),
        "retained reads": (enabled and config["reuse_read_expectations"],
                           r"\b(?:mark_covered|retained_size|uncovered|first_uncovered|covered_match)\b", source),
        "write state": (enabled and config["mode"] == "state", r"\bput_latest\b", source),
        "multiset candidate search": (enabled and config["mode"] == "set", r"if\(!equal\)", source),
        "packet masks": (enabled and not config["atomize"], r"\b(?:genables|menables)\b", equal),
        "copy helper": (enabled and (not config["atomize"] or callback), r"\bcopy_payload\b", adapter),
        "response comparison": (enabled and config["compare_response"], r"get_response_status\s*\(", equal),
        "address comparison": (enabled and config["compare_address"] and
                               (config["mode"] == "ordered" or not config["match_address"]),
                               r"golden\.get_address\s*\(", equal),
        "command comparison": (enabled and config["mode"] != "state" and
                               (config["compare_command"] or config["reuse_read_expectations"]) and
                               (config["mode"] == "ordered" or not
                                (config["match_command"] or config["reuse_read_expectations"])),
                               r"golden\.get_command\s*\(", equal),
        "data comparison": (enabled and config["compare_data"], r"\bgdata\b", equal),
        "drop accounting": (enabled and config["monitor_policy"] == "drop", r"\bdropped_count\b", source),
    }
    obligations.update({
        report: (enabled and selected, rf'"GP_{report}"', source)
        for report, selected in {
            "COUNT": config["check_count"], "MISSING": config["check_missing"],
            "UNEXPECTED": config["check_unexpected"],
            "EMPTY_GOLDEN": config["require_golden"] and not explicit,
            "NO_MATCH": config["require_match"] and not explicit,
        }.items()
    })
    for report in ("COUNT", "MISSING", "UNEXPECTED", "EMPTY_GOLDEN", "NO_MATCH"):
        selected = obligations[report][0]
        obligations[f"{report} predicate"] = (selected, rf"issues\s*\|=\s*{report}\b", source)
        obligations[f"{report} state"] = (selected, rf"\blocalparam[^\n]+\b{report}\b", source)
    leaked = [name for name, (want, pattern, body) in obligations.items()
              if not want and re.search(pattern, body)]
    missing = [name for name, (want, pattern, body) in obligations.items()
               if want and not re.search(pattern, body)]
    if missing or leaked:
        raise ValueError(f"missing feature witnesses: {missing}; disabled feature witnesses: {leaked}")
    prefix = config["class_prefix"]
    return (len(obligations), sum(not want for want, _, _ in obligations.values()),
            sum(len(text.replace(prefix + "scoreboard", "scoreboard")) for text in products.values()))


def calibrate(products: dict[str, str], config: dict, profile: str) -> int:
    """Prove that the gate rejects emitted garbage and missing selected code."""
    bad = (
        {**products, "config.sv": "class leaked; endclass\n"},
        {**products, "scoreboard.sv": products["scoreboard.sv"] + "\nuvm_config_db #(bit) leak;\n"},
        {**products, "scoreboard.sv": products["scoreboard.sv"].replace("GP_COUNT", "LOST_COUNT")},
        {**products, "all.f": products["all.f"] + "\nconfig.sv"},
    ) if profile == "reference" else (
        {**products, "scoreboard.sv": products["scoreboard.sv"] + "\nif(0) $display(\"hidden\");\n"},
        {**products, "scoreboard.sv": products["scoreboard.sv"] + "\nlocalparam bit MISSING = 1;\n"},
        {**products, "scoreboard.sv": products["scoreboard.sv"] + "\nfunction void print_payload(); endfunction\n"},
    )
    for candidate in bad:
        try:
            inspect(candidate, config)
        except ValueError:
            continue
        raise ValueError("gate accepted a deliberately damaged generated product")
    return len(bad)


def run_matrix(executable: str, output: Path) -> dict:
    """Render each configuration into a fresh directory and inspect its products."""
    output = output.resolve()
    results = {}
    controls = 0
    for name, overrides in PROFILES.items():
        config = BASE | overrides | {"class_prefix": "general_" if name == "example" else f"{name}_"}
        yaml = FAMILY / "example.yaml" if name == "example" else output / f"{name}.yaml"
        if name != "example":
            yaml.write_text(json.dumps(config, indent=2), encoding="utf-8")
        destination = output / name
        if destination.exists():
            raise ValueError(f"output must be fresh: {destination}")
        result = subprocess.run([executable, str(FAMILY), str(yaml), str(destination)],
                                capture_output=True, timeout=20)
        if result.returncode:
            raise ValueError(f"{name} failed to render: {result.stderr.decode(errors='replace')}")
        products = {p.name: p.read_text(encoding="utf-8") for p in destination.iterdir()}
        try:
            witnesses, disabled, characters = inspect(products, config)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
        results[name] = dict(nonempty_files=len(products), source_characters=characters,
                             disabled_feature_leaks=0, disabled_contracts=disabled,
                             redundancy_ratio=0 / disabled, feature_contracts=witnesses)
        if name in {"reference", "lean"}:
            controls += calibrate(products, config, name)
    if results["off"]["source_characters"] >= results["lean"]["source_characters"]:
        raise ValueError("disabled profile did not remove comparison source")
    if results["lean"]["source_characters"] >= results["reference"]["source_characters"]:
        raise ValueError("lean profile did not reduce the reference output")
    return dict(passed=True, profiles=results, rejected_controls=controls)


def main() -> None:
    """Run the renderer matrix and return nonzero on a missing or leaked capability."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    executable = renderer()
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        receipt = run_matrix(executable, args.output)
    else:
        with tempfile.TemporaryDirectory(prefix="scoreboard-generation-") as directory:
            receipt = run_matrix(executable, Path(directory))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

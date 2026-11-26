#!/usr/bin/env python3
"""Discover affected template families and enforce their generated feature contracts."""
from __future__ import annotations

import argparse
import ast
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "generation.contract.json"
INPUTS = {"example.yaml", "models.py", CONTRACT}
SOURCE = re.compile(r"\{%[-+]?\s*(?:if|elif)\b|\{\{[^\n]*\bif\b")
CONDITION = re.compile(r"\{%[-+]?\s*(?:if|elif)\s+(.+?)%\}")


def git_paths(*args: str) -> list[str]:
    """Read paths with NUL delimiters so names survive quoting and spaces."""
    result = subprocess.run(["git", *args, "-z"], cwd=ROOT, capture_output=True, check=True)
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def affected(paths: list[str]) -> set[Path]:
    """Resolve each changed template input to its closest generator entry."""
    families = set()
    for name in paths:
        path = ROOT / name
        if not path.is_relative_to(ROOT / "src"):
            continue
        if path.suffix not in {".j2", ".py", ".yaml", ".yml"} and path.name != CONTRACT:
            continue
        if path.name.startswith("."):
            continue
        candidates = [p for p in path.parents if p.is_relative_to(ROOT / "src") and p != ROOT / "src"]
        owners = [p for p in candidates if any((p / entry).is_file() for entry in INPUTS)]
        if owners:
            family = owners[0]
        elif path.suffix == ".j2" or path.name == CONTRACT:
            family = path.parent
        else:
            continue
        if any(family.rglob("*.j2")):
            families.add(family)
    return families


def require_staged_inputs(families: set[Path]) -> None:
    """Reject a staged submission that would depend on unstaged generation inputs."""
    dirty = affected(git_paths("diff", "--name-only") +
                     git_paths("ls-files", "--others", "--exclude-standard"))
    if pending := dirty & families:
        raise ValueError("stage the complete template inputs for: " +
                         ", ".join(p.relative_to(ROOT).as_posix() for p in sorted(pending)))


def renderer() -> str:
    """Resolve the actual project renderer."""
    selected = os.environ.get("JINJA_BUILD_EXECUTABLE")
    local = ROOT / ".codex/toolchain.local.json"
    if selected is None and local.is_file():
        selected = json.loads(local.read_text(encoding="utf-8")).get("jinja_build")
    executable = shutil.which(selected or "jinja-build")
    if not executable:
        raise ValueError("Set JINJA_BUILD_EXECUTABLE or .codex/toolchain.local.json")
    return executable


def inspect_output(files: dict[str, str], contract: dict, profile: dict) -> dict:
    """Verify exact files, dependency lists, and positive and negative feature witnesses."""
    expected = profile.get("files", contract.get("files", []))
    if not expected or set(files) != set(expected) or any(not text.strip() for text in files.values()):
        raise ValueError("generated file set differs from contract or contains an empty product")
    for name, entries in profile.get("filelists", contract.get("filelists", {})).items():
        if files[name].splitlines() != entries:
            raise ValueError(f"incorrect filelist {name}")
    code = {name: re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", text)
            for name, text in files.items()}
    if any(re.search(r"\bif\s*\(\s*(?:0|1|1'b[01])\s*\)", code[name])
           for name in code if name.endswith((".sv", ".svh"))):
        raise ValueError("constant runtime branch in generated SystemVerilog")
    result = dict(disabled=0, leaked=0, missing=0)
    errors = []
    for feature, witnesses in contract["features"].items():
        enabled = profile["settings"][feature]
        for name, pattern in witnesses:
            found = bool(re.search(pattern, code.get(name, ""), re.M))
            result["disabled"] += not enabled
            result["leaked"] += found and not enabled
            result["missing"] += enabled and not found
            if found != enabled:
                errors.append(f"{feature}: {name} / {pattern}")
    if errors:
        raise ValueError(f"{result}; feature obligations failed: {errors}")
    return {**result, "redundancy_ratio": result["leaked"] / result["disabled"] if result["disabled"] else None,
            "files": len(files), "characters": sum(map(len, files.values()))}


def run_contract(family: Path, contract: dict) -> dict:
    """Render from a fresh directory for each profile and check the pairwise evidence."""
    features = contract["features"]
    profiles = contract["profiles"]
    if not profiles or any(not witnesses for witnesses in features.values()):
        raise ValueError("empty checks or missing profiles")
    settings = [p["settings"] for p in profiles.values()]
    if any(set(s) != set(features) or any(type(v) is not bool for v in s.values()) for s in settings):
        raise ValueError("profile is missing a feature or contains a nonboolean feature value")
    values = {tuple(s[k] for k in features) for s in settings}
    if len(features) <= 4 and values != set(product((False, True), repeat=len(features))):
        raise ValueError("profiles must demonstrate every combination for up to four binary features")
    for feature in features:
        if not any(not a[feature] and b == (a | {feature: True}) for a in settings for b in settings):
            raise ValueError(f"missing one-switch on/off comparison for {feature}")
    if features and ({k: False for k in features} not in settings or {k: True for k in features} not in settings):
        raise ValueError("missing all-on or all-off profile")
    reports = {}
    products = {}
    example = contract.get("example_profile")
    if example is not None and (example not in profiles or not (family / "example.yaml").is_file()):
        raise ValueError("example_profile requires a named profile and example.yaml")
    executable = renderer()
    with tempfile.TemporaryDirectory(prefix="template-pruning-") as temp:
        root = Path(temp)
        for index, (name, profile) in enumerate(profiles.items()):
            config = family / "example.yaml" if name == example else root / f"{index}.yaml"
            if name != example:
                config.write_text(json.dumps(contract.get("base_input", {}) |
                                              profile.get("input", profile["settings"])), encoding="utf-8")
            output = root / str(index)
            run = subprocess.run([executable, str(family), str(config), str(output)], cwd=ROOT,
                                 capture_output=True, timeout=25)
            if run.returncode:
                raise ValueError(f"{name} render failed: {(run.stdout + run.stderr).decode(errors='replace')}")
            files = {p.relative_to(output).as_posix(): p.read_text(encoding="utf-8")
                     for p in output.rglob("*") if p.is_file()}
            reports[name] = inspect_output(files, contract, profile)
            products[name] = files
    controls = 0
    for feature, witnesses in features.items():
        on = next(name for name, p in profiles.items() if p["settings"][feature])
        off = next(name for name, p in profiles.items() if not p["settings"][feature])
        path, pattern = witnesses[0]
        # Copy a real matching line or file from the enabled output into the disabled one.
        snippet = re.search(pattern, products[on][path], re.M).group(0)
        invalid = dict(products[off])
        invalid[path] = invalid.get(path, "") + "\n" + snippet
        try:
            inspect_output(invalid, contract, profiles[off])
        except ValueError:
            controls += 1
        else:
            raise ValueError(f"leak calibration did not reject {feature}")
        invalid = dict(products[on])
        invalid[path] = re.sub(pattern, "", invalid[path], flags=re.M)
        try:
            inspect_output(invalid, contract, profiles[on])
        except ValueError:
            controls += 1
        else:
            raise ValueError(f"missing-feature calibration did not reject {feature}")
    return {"profiles": reports, "rejected_controls": controls,
            "products_sha256": {name: hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
                                for name, files in products.items()}}


def check_family(family: Path) -> dict:
    """Require a contract for conditional generation and dispatch its validator."""
    contract_path = family / CONTRACT
    templates = "\n".join(p.read_text(encoding="utf-8-sig") for p in family.rglob("*.j2"))
    optional = bool(SOURCE.search(templates))
    if not contract_path.is_file():
        if optional:
            raise ValueError(f"missing conditional output contract: {contract_path.relative_to(ROOT)}")
        return {"scope": "no detected conditional generation"}
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.pop("version", None) != 1:
        raise ValueError(f"invalid contract version: {contract_path.relative_to(ROOT)}")
    if "validator" in contract:
        path = contract.pop("validator")
        if contract or not re.fullmatch(r"tools/check_[a-z0-9_]+\.py", path) or path.endswith("/check_template_pruning.py"):
            raise ValueError("invalid validator")
        run = subprocess.run([sys.executable, str(ROOT / path)], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=75)
        if run.returncode:
            raise ValueError(run.stdout + run.stderr)
        result = json.loads(run.stdout)
        if (result.get("passed") is not True or result.get("family") != family.relative_to(ROOT).as_posix()
                or not result.get("profiles") or result.get("rejected_controls", 0) < 2):
            raise ValueError("family validator did not report a successful matrix for this family")
        return result
    if set(contract) - {"base_input", "features", "profiles", "files", "filelists", "example_profile"} or (
        optional and not contract.get("features")
    ):
        raise ValueError("invalid contract keys or conditional family without feature witnesses")
    model = family / "models.py"
    if model.is_file():
        schema = ast.parse(model.read_text(encoding="utf-8-sig"))
        boolean_fields = {node.target.id for cls in schema.body if isinstance(cls, ast.ClassDef) and cls.name == "Models"
                          for node in cls.body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                          and isinstance(node.annotation, ast.Name) and node.annotation.id == "bool"}
        used = {token for match in CONDITION.findall(templates) for token in re.findall(r"\b\w+\b", match)}
        if untested := (boolean_fields & used) - set(contract["features"]):
            raise ValueError(f"conditional model fields lack witnesses: {sorted(untested)}")
    return run_contract(family, contract)


def inventory() -> dict[str, list[str]]:
    """List conditional families with and without a local generation contract."""
    groups: dict[str, list[str]] = {"registered": [], "pending": []}
    for family in sorted(affected(git_paths("ls-files"))):
        if (family / CONTRACT).is_file():
            groups["registered"].append(family.relative_to(ROOT).as_posix())
        elif any(SOURCE.search(p.read_text(encoding="utf-8-sig")) for p in family.rglob("*.j2")):
            groups["pending"].append(family.relative_to(ROOT).as_posix())
    return groups


def main() -> None:
    """Validate staged, working and outgoing families selected by the caller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    if args.inventory:
        if args.family or args.staged:
            parser.error("--inventory is exclusive")
        print(json.dumps(inventory(), indent=2))
        return
    if args.family:
        families = {(ROOT / name).resolve() for name in args.family}
        if any(not p.is_relative_to(ROOT / "src") or not p.is_dir() for p in families):
            parser.error("--family must name a directory under src")
    else:
        paths = git_paths("diff", "--cached", "--name-only")
        if not args.staged:
            paths += git_paths("diff", "--name-only") + git_paths("ls-files", "--others", "--exclude-standard")
            if subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT,
                              capture_output=True).returncode == 0:
                paths += git_paths("diff", "--name-only", "origin/main..HEAD")
        families = affected(paths)
        if "tools/check_template_pruning.py" in paths or "tools/check_scoreboard_generation.py" in paths:
            families.update(p.parent for p in (ROOT / "src").rglob(CONTRACT))
        if args.staged:
            require_staged_inputs(families)
    print(json.dumps({"passed": True, "families": {
        family.relative_to(ROOT).as_posix(): check_family(family) for family in sorted(families)
    }}, indent=2))


if __name__ == "__main__":
    main()

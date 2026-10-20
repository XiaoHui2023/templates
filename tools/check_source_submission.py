#!/usr/bin/env python3
"""Write a challenge-bound receipt after the repository source checks pass."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / ".codex" / "quality-gate.json"


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=capture)


def artifact_tree() -> str:
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, capture_output=True)
    tracked_args = ["git", "diff", "--binary", "--no-ext-diff"]
    if head.returncode == 0:
        tracked_args.append("HEAD")
    tracked = run(*tracked_args, capture=True)
    cached = run("git", "diff", "--cached", "--binary", "--no-ext-diff", capture=True)
    status = run("git", "status", "--porcelain=v2", "-z", "--untracked-files=all", capture=True)
    untracked = hashlib.sha256()
    for record in status.stdout.split(b"\0"):
        if not record.startswith(b"? "):
            continue
        relative = os.fsdecode(record[2:])
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"untracked entry is not a regular file: {relative}")
        untracked.update(record[2:] + b"\0" + hashlib.sha256(path.read_bytes()).digest() + b"\0")
    digest = hashlib.sha256()
    for label, value in (
        (b"head", head.stdout if head.returncode == 0 else b"<unborn>"),
        (b"tracked", tracked.stdout),
        (b"cached", cached.stdout),
        (b"status", status.stdout),
        (b"untracked-content", untracked.digest()),
    ):
        digest.update(label + b"\0" + value + b"\0")
    return "git-state-sha256:" + digest.hexdigest()


def artifact_hashes(policy: dict[str, Any]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for relative in policy.get("artifact_paths", []):
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents or path.is_dir():
            raise ValueError(f"invalid artifact path: {relative}")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def validate_source() -> None:
    run("git", "diff", "--check")
    for path in (ROOT / "src").rglob("*.py"):
        compile(path.read_text(encoding="utf-8-sig"), str(path), "exec", dont_inherit=True)


def main() -> int:
    challenge = os.environ.get("CODEX_GATE_CHALLENGE")
    phase = os.environ.get("CODEX_GATE_PHASE", "delivery")
    if phase not in {"source", "delivery"} or not challenge:
        raise ValueError("this validator must run from the managed quality gate")
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    validate_source()
    source = policy["source_submission"]
    if phase == "source":
        command = source["command_windows"] if os.name == "nt" else source["command"]
        receipt_path = ROOT / source["receipt"]
        receipt = {
            "schema_version": "agent-source-ready/1",
            "status": "source-ready",
            "claim_scope": "source-checkpoint",
            "challenge": challenge,
            "policy_sha256": canonical_sha256(policy),
            "command_sha256": canonical_sha256(command),
            "validator_id": source["validator_id"],
            "artifact_tree": artifact_tree(),
            "artifact_hashes": artifact_hashes(policy),
        }
    else:
        command = policy["delivery_command_windows"] if os.name == "nt" else policy["delivery_command"]
        receipt_path = ROOT / policy["ready_receipt"]
        receipt = {
            "schema_version": 2,
            "status": "delivery-ready",
            "challenge": challenge,
            "policy_sha256": canonical_sha256(policy),
            "delivery_command_sha256": canonical_sha256(command),
            "validator_id": policy["validator_id"],
            "artifact_tree": artifact_tree(),
            "artifact_hashes": artifact_hashes(policy),
        }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{phase} validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

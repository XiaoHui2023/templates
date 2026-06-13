from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_PKG_DIR = Path(__file__).resolve().parent


def _repo_root() -> Path:
    for parent in _PKG_DIR.parents:
        if (parent / "src" / "c" / "pll_mini").is_dir():
            return parent
    return _PKG_DIR.parents[2]


def bin_dir() -> Path:
    """返回 consolver 与 ralf-conv 所在目录。"""
    override = os.environ.get("PLL_MINI_BIN_DIR")
    if override:
        return Path(override)
    platform_dir = "windows" if sys.platform == "win32" else "linux"
    pkg_bin = _PKG_DIR / "bin" / platform_dir
    if sys.platform == "win32" and not _has_tool(pkg_bin):
        win = _repo_root() / "test" / "c" / "pll_mini" / "bin" / "windows"
        if _has_tool(win):
            return win
    return pkg_bin


def _has_tool(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return consolver_path(directory).is_file() and ralfconv_path(directory).is_file()


def _tool_name(base: str) -> str:
    if sys.platform == "win32":
        return f"{base}.exe"
    return base


def consolver_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    return root / _tool_name("consolver")


def ralfconv_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    return root / _tool_name("ralf-conv")


def run_consolver_solve(
    smt2_text: str,
    *,
    timeout_ms: int | None = None,
) -> Mapping[str, Any]:
    """调用 consolver 求解 SMT-LIB 文本并解析 JSON 结果。"""
    exe = consolver_path()
    if not exe.is_file():
        raise FileNotFoundError(f"找不到 consolver 可执行文件: {exe}")
    cmd = [str(exe), "solve", "--input-text", smt2_text]
    if timeout_ms is not None:
        cmd.extend(["--timeout-ms", str(timeout_ms)])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"consolver 退出码 {proc.returncode}: {detail or '无输出'}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"consolver 输出不是合法 JSON: {proc.stdout[:200]!r}"
        ) from exc
    status = payload.get("status")
    if status != "sat":
        reason = payload.get("reason", "")
        raise RuntimeError(
            f"时钟树约束不可满足: status={status!r} {reason}".strip()
        )
    model = payload.get("model")
    if not isinstance(model, dict):
        raise RuntimeError(f"consolver 返回缺少 model 字段: {payload!r}")
    return model


def run_ralfconv_flat(
    ralf_path: Path,
    *,
    include_dirs: Sequence[Path] = (),
    base_offset: int = 0,
) -> str:
    """调用 ralf-conv 把 RALF 转为 flat JSON 文本。"""
    exe = ralfconv_path()
    if not exe.is_file():
        raise FileNotFoundError(f"找不到 ralf-conv 可执行文件: {exe}")
    if not ralf_path.is_file():
        raise FileNotFoundError(f"RALF 文件不存在: {ralf_path}")
    cmd = [
        str(exe),
        "-i",
        str(ralf_path),
        "--format",
        "flat",
        "-b",
        str(base_offset),
    ]
    for inc in include_dirs:
        cmd.extend(["-I", str(inc)])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"ralf-conv 退出码 {proc.returncode}: {detail or '无输出'}"
        )
    return proc.stdout

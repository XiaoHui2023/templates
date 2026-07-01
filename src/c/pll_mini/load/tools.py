from __future__ import annotations

import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

_PKG_ROOT = Path(__file__).resolve().parent.parent

_RALFCONV_URL = "https://github.com/XiaoHui2023/ralfconv"
_CONSOLVER_URL = "https://github.com/XiaoHui2023/consolver"


def _format_stage_fields(fields: Mapping[str, object]) -> str:
    if not fields:
        return ""
    return "; " + "; ".join(f"{key}={value}" for key, value in fields.items())


def log_stage_start(
    component: str,
    action: str,
    label: str,
    **fields: object,
) -> float:
    """Print a timed stage start line.

    Args:
        component: Log component name.
        action: Action name within the component.
        label: Human-readable stage label.
        fields: Extra values appended to the line.

    Returns:
        float: Timer value for the matching completion line.
    """
    from report.ui import active_progress_session

    session = active_progress_session()
    if session is not None:
        started = session.stage_start(component, action, label, **fields)
        if session.enabled:
            return started
    print(
        f"[pll_mini] {component} {action} start: {label}"
        f"{_format_stage_fields(fields)}",
        file=sys.stderr,
        flush=True,
    )
    return time.perf_counter()


def log_stage_done(
    component: str,
    action: str,
    label: str,
    started_at: float,
    **fields: object,
) -> None:
    """Print a timed stage completion line.

    Args:
        component: Log component name.
        action: Action name within the component.
        label: Human-readable stage label.
        started_at: Timer value returned by the start logger.
        fields: Extra values appended to the line.
    """
    from report.ui import active_progress_session

    session = active_progress_session()
    if session is not None:
        session.stage_done(component, action, label, started_at, **fields)
        if session.enabled:
            return
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    print(
        f"[pll_mini] {component} {action} done: {label}; "
        f"elapsed_ms={elapsed_ms}{_format_stage_fields(fields)}",
        file=sys.stderr,
        flush=True,
    )


def log_stage_progress(
    component: str,
    action: str,
    label: str,
    **fields: object,
) -> None:
    """Print or refresh a timed stage progress line."""
    from report.ui import active_progress_session

    session = active_progress_session()
    if session is not None:
        session.stage_progress(component, action, label, **fields)
        if session.enabled:
            return
    print(
        f"[pll_mini] {component} {action} progress: {label}"
        f"{_format_stage_fields(fields)}",
        file=sys.stderr,
        flush=True,
    )


def bin_dir() -> Path:
    """返回 ralfconv 所在目录。"""
    root = _PKG_ROOT / "bin"
    if sys.platform != "win32" and root.is_dir():
        for entry in root.iterdir():
            if entry.is_file():
                _ensure_executable(entry)
    return root


def _tool_name(base: str) -> str:
    if sys.platform == "win32":
        return f"{base}.exe"
    return base


def _ensure_executable(path: Path) -> None:
    """非 Windows 上 clone 后若无执行位则补上，避免 core.filemode=false 等情形。"""
    if sys.platform == "win32" or not path.is_file():
        return
    if os.access(path, os.X_OK):
        return
    try:
        mode = path.stat().st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        return


def _missing_tool_error(tool: str, url: str, exe: Path) -> FileNotFoundError:
    bindir = bin_dir()
    return FileNotFoundError(
        f"找不到 {tool} 可执行文件: {exe}\n"
        f"请从 {url} 下载，将可执行文件放到 {bindir}"
    )


def ralfconv_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    path = root / _tool_name("ralfconv")
    _ensure_executable(path)
    return path


def consolver_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    path = root / _tool_name("consolver")
    _ensure_executable(path)
    return path


def run_ralfconv_flat(
    ralf_path: Path,
    *,
    include_dirs: Sequence[Path] = (),
    base_offset: int = 0,
) -> str:
    """调用 ralfconv 把 RALF 转为 flat JSON 文本。"""
    exe = ralfconv_path()
    if not exe.is_file():
        raise _missing_tool_error("ralfconv", _RALFCONV_URL, exe)
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
    started_at = log_stage_start(
        "ralfconv",
        "flat",
        str(ralf_path),
        base_offset=base_offset,
        include_dirs=len(include_dirs),
    )
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_stage_done(
        "ralfconv",
        "flat",
        str(ralf_path),
        started_at,
        returncode=proc.returncode,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"ralfconv 退出码 {proc.returncode}: {detail or '无输出'}"
        )
    return proc.stdout


def run_consolver_solve(
    smt2_path: Path,
    *,
    timeout_ms: int | None = None,
) -> str:
    """Call consolver once and return JSON text."""
    exe = consolver_path()
    if not exe.is_file():
        raise _missing_tool_error("consolver", _CONSOLVER_URL, exe)
    if not smt2_path.is_file():
        raise FileNotFoundError(f"SMT-LIB 文件不存在: {smt2_path}")
    cmd = [str(exe), "solve", str(smt2_path), "--format", "json"]
    if timeout_ms is not None:
        cmd.extend(["--timeout-ms", str(timeout_ms)])
    started_at = log_stage_start(
        "consolver",
        "solve",
        str(smt2_path),
        timeout_ms=timeout_ms or 0,
    )
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_stage_done(
        "consolver",
        "solve",
        str(smt2_path),
        started_at,
        returncode=proc.returncode,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"consolver 退出码 {proc.returncode}: {detail or '无输出'}"
        )
    return proc.stdout

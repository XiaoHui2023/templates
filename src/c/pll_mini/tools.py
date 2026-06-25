from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

_PKG_DIR = Path(__file__).resolve().parent

_CONSOLVER_URL = "https://github.com/XiaoHui2023/consolver"
_RALFCONV_URL = "https://github.com/XiaoHui2023/ralfconv"


def bin_dir() -> Path:
    """返回 consolver 与 ralfconv 所在目录。"""
    root = _PKG_DIR / "bin"
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


def consolver_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    path = root / _tool_name("consolver")
    _ensure_executable(path)
    return path


def ralfconv_path(base: Path | None = None) -> Path:
    root = base if base is not None else bin_dir()
    path = root / _tool_name("ralfconv")
    _ensure_executable(path)
    return path


def run_consolver_solve(
    smt2_text: str,
    *,
    label: str = "constraints",
    timeout_ms: int | None = None,
) -> Mapping[str, Any]:
    """调用 consolver 求解 SMT-LIB 文本并解析 JSON 结果。"""
    exe = consolver_path()
    if not exe.is_file():
        raise _missing_tool_error("consolver", _CONSOLVER_URL, exe)
    started_at = time.perf_counter()
    line_count = smt2_text.count("\n")
    print(
        f"[pll_mini] consolver solve start: {label}; "
        f"lines={line_count}; timeout_ms={timeout_ms}",
        file=sys.stderr,
        flush=True,
    )
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".smt2",
            delete=False,
        ) as tmp:
            tmp.write(smt2_text)
            tmp_path = Path(tmp.name)
        cmd = [str(exe), "solve", str(tmp_path)]
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
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    print(
        f"[pll_mini] consolver solve done: {label}; "
        f"elapsed_ms={elapsed_ms}; returncode={proc.returncode}",
        file=sys.stderr,
        flush=True,
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
        if status == "unsat":
            headline = "时钟树约束互相矛盾，无解"
        elif status == "unknown":
            headline = "时钟树约束求解超时或无法判定"
        else:
            headline = f"时钟树约束求解失败: status={status!r}"
        detail = f"{headline}"
        if reason:
            detail = f"{detail}；{reason}"
        raise RuntimeError(detail)
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
            f"ralfconv 退出码 {proc.returncode}: {detail or '无输出'}"
        )
    return proc.stdout

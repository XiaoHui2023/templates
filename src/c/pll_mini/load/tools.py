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
    smt2_text: str,
    *,
    timeout_ms: int | None = None,
) -> str:
    """Solve SMT-LIB text once and return consolver-compatible JSON text."""
    started_at = log_stage_start(
        "consolver",
        "solve",
        "input-text",
        bytes=len(smt2_text.encode("utf-8")),
        timeout_ms=timeout_ms or 0,
    )
    raw = _solve_smt2_text_json(smt2_text, timeout_ms=timeout_ms)
    log_stage_done(
        "consolver",
        "solve",
        "input-text",
        started_at,
        returncode=0,
    )
    return raw


def _solve_smt2_text_json(
    smt2_text: str,
    *,
    timeout_ms: int | None,
) -> str:
    import json
    try:
        import z3
    except ModuleNotFoundError:
        return _solve_smt2_text_json_subprocess(smt2_text, timeout_ms=timeout_ms)

    solver = z3.Solver()
    if timeout_ms is not None:
        if timeout_ms <= 0:
            raise ValueError("consolver timeout_ms must be positive")
        solver.set(timeout=timeout_ms)

    solver.add(z3.parse_smt2_string(smt2_text))
    result = solver.check()
    if result == z3.sat:
        data = {"status": "sat", "model": _z3_model_to_python(solver.model())}
    elif result == z3.unsat:
        data = {"status": "unsat", "model": {}}
    else:
        data = {"status": "unknown", "model": {}}
        reason = solver.reason_unknown() or None
        if reason:
            data["reason"] = reason
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _solve_smt2_text_json_subprocess(
    smt2_text: str,
    *,
    timeout_ms: int | None,
) -> str:
    code = '\nimport json\nimport sys\nimport z3\n\n\ndef value_to_python(value):\n    if z3.is_true(value):\n        return True\n    if z3.is_false(value):\n        return False\n    if z3.is_int_value(value):\n        return value.as_long()\n    if z3.is_rational_value(value):\n        numerator = value.numerator_as_long()\n        denominator = value.denominator_as_long()\n        return numerator if denominator == 1 else numerator / denominator\n    if z3.is_bv_value(value):\n        width = value.size()\n        digits = max(1, (width + 3) // 4)\n        return {\n            "value": value.as_long(),\n            "hex": f"0x{value.as_long():0{digits}x}",\n            "width": width,\n        }\n    return str(value)\n\n\ntimeout_ms = int(sys.argv[1]) if len(sys.argv) > 1 else 0\ntext = sys.stdin.read()\nsolver = z3.Solver()\nif timeout_ms > 0:\n    solver.set(timeout=timeout_ms)\nsolver.add(z3.parse_smt2_string(text))\nresult = solver.check()\nif result == z3.sat:\n    model = {}\n    z3_model = solver.model()\n    for decl in sorted(z3_model.decls(), key=lambda item: item.name()):\n        interp = z3_model[decl]\n        if interp is not None:\n            model[decl.name()] = value_to_python(interp)\n    data = {"status": "sat", "model": model}\nelif result == z3.unsat:\n    data = {"status": "unsat", "model": {}}\nelse:\n    data = {"status": "unknown", "model": {}}\n    reason = solver.reason_unknown() or None\n    if reason:\n        data["reason"] = reason\nprint(json.dumps(data, ensure_ascii=False, indent=2))\n'
    cmd = ["python", "-c", code]
    if timeout_ms is not None:
        cmd.append(str(timeout_ms))
    proc = subprocess.run(
        cmd,
        input=smt2_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"consolver string subprocess failed with code {proc.returncode}: "
            f"{detail or 'no output'}"
        )
    return proc.stdout


def _z3_model_to_python(model: object) -> dict[str, object]:
    import z3

    values: dict[str, object] = {}
    for decl in sorted(model.decls(), key=lambda item: item.name()):
        interp = model[decl]
        if interp is None:
            continue
        if z3.is_true(interp):
            values[decl.name()] = True
        elif z3.is_false(interp):
            values[decl.name()] = False
        elif z3.is_int_value(interp):
            values[decl.name()] = interp.as_long()
        elif z3.is_rational_value(interp):
            numerator = interp.numerator_as_long()
            denominator = interp.denominator_as_long()
            values[decl.name()] = numerator if denominator == 1 else numerator / denominator
        elif z3.is_bv_value(interp):
            width = interp.size()
            digits = max(1, (width + 3) // 4)
            values[decl.name()] = {
                "value": interp.as_long(),
                "hex": f"0x{interp.as_long():0{digits}x}",
                "width": width,
            }
        else:
            values[decl.name()] = str(interp)
    return values

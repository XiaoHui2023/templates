from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from ralf_model.errors import RalfSourceError

# RALF 常作为 Tcl 脚本；顶层 ``source path`` 常见单独成行（可有尾随 ``;``、``#`` 注释）。
_SOURCE_HEAD = re.compile(r"^source\s+", re.IGNORECASE)


def resolve_source_path(
    spec: str,
    *,
    base_dir: Path,
    include_paths: Sequence[Path],
) -> Path:
    """按 Synopsys ``ralgen -I`` 语义解析 ``source`` 路径。

    顺序：``base_dir / spec``（当前文件所在目录），然后各 ``include_paths / spec``。
    ``spec`` 为绝对路径时直接查找该路径。
    """
    raw = spec.strip()
    if not raw:
        raise RalfSourceError("source 路径为空")

    p = Path(raw)
    if p.is_absolute():
        if p.is_file():
            return p.resolve()
        raise RalfSourceError(f"找不到 source 文件: {p}", path=p)

    candidates = [base_dir / raw, *[inc / raw for inc in include_paths]]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    searched = [str(x) for x in candidates]
    raise RalfSourceError(
        f"找不到 source 文件: {raw!r}，已搜索: {searched}",
        path=base_dir / raw,
    )


def _strip_line_comment(line: str) -> str:
    if "#" not in line:
        return line
    i = line.index("#")
    # Tcl 里字符串中的 # 不一定是注释；简化处理：引号外的第一个 #
    in_dq = False
    j = 0
    while j < len(line):
        c = line[j]
        if c == '"' and (j == 0 or line[j - 1] != "\\"):
            in_dq = not in_dq
        elif c == "#" and not in_dq:
            return line[:j].rstrip()
        j += 1
    return line


def _parse_source_argument(line: str) -> str | None:
    """若整行（去掉注释后）为 ``source <path>``，返回路径规格，否则返回 None。"""
    s = _strip_line_comment(line).strip()
    if not s:
        return None
    s = s.rstrip(";").strip()
    m = _SOURCE_HEAD.match(s)
    if not m:
        return None
    rest = s[m.end() :].strip()
    if not rest:
        return None
    if rest.startswith('"'):
        end = rest.find('"', 1)
        if end == -1:
            raise RalfSourceError(f"source 双引号路径未闭合: {line!r}")
        inner = rest[1:end]
        tail = rest[end + 1 :].strip().rstrip(";").strip()
        if tail:
            raise RalfSourceError(f"source 行含多余内容: {line!r}")
        return inner
    if rest.startswith("{"):
        depth = 0
        i = 0
        while i < len(rest):
            if rest[i] == "{":
                depth += 1
            elif rest[i] == "}":
                depth -= 1
                if depth == 0:
                    inner = rest[1:i]
                    tail = rest[i + 1 :].strip().rstrip(";").strip()
                    if tail:
                        raise RalfSourceError(f"source 行含多余内容: {line!r}")
                    return inner.strip()
            i += 1
        raise RalfSourceError(f"source 花括号路径未闭合: {line!r}")
    parts = rest.split()
    if len(parts) != 1:
        raise RalfSourceError(f"无法解析的 source 行（期望单个路径）: {line!r}")
    return parts[0]


def expand_ralf_sources(
    text: str,
    *,
    current_file: Path,
    include_paths: Sequence[Path] = (),
    encoding: str = "utf-8",
    _chain: tuple[Path, ...] = (),
) -> tuple[str, list[tuple[Path, int]]]:
    """将 Tcl 风格 ``source path`` 递归展开为单段 RALF 文本后再交给 ``parse_ralf``。

    ``current_file`` 用于确定相对路径的基准目录（通常为 ``path.parent``），并参与循环检测。
    从内存加载字符串时可使用 ``base_dir / \"__inline__.ralf\"`` 这类占位路径。

    返回 ``(展开后文本, 行来源)``：``行来源[i]`` 为 ``(源文件路径, 该文件内行号)``，
    对应展开结果第 ``i+1`` 行；``source`` 指令行本身不占展开结果行，但其行号仍计入宿主文件行序。
    """
    cf = current_file.resolve()
    if cf in _chain:
        raise RalfSourceError(f"source 形成循环: {' -> '.join(str(p) for p in _chain)} -> {cf}", path=cf)

    chain = _chain + (cf,)
    inc = tuple(Path(p).resolve() for p in include_paths)

    out: list[str] = []
    line_origins: list[tuple[Path, int]] = []
    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        spec = _parse_source_argument(line)
        if spec is None:
            out.append(line)
            line_origins.append((cf, line_no))
            continue

        inner_path = resolve_source_path(spec, base_dir=cf.parent, include_paths=inc)
        inner_text = inner_path.read_text(encoding=encoding)
        expanded_inner, inner_origins = expand_ralf_sources(
            inner_text,
            current_file=inner_path,
            include_paths=inc,
            encoding=encoding,
            _chain=chain,
        )
        out.append(expanded_inner)
        line_origins.extend(inner_origins)
        if expanded_inner and not expanded_inner.endswith("\n"):
            out.append("\n")
            line_origins.append(
                inner_origins[-1] if inner_origins else (inner_path, 1)
            )

    return "".join(out), line_origins

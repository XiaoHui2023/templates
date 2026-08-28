from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ralf_model.emit import dump_ralf
from ralf_model.nodes import RalfDocument
from ralf_model.parse import parse_ralf
from ralf_model.source_expand import expand_ralf_sources


def load_ralf_file(
    path: str | Path,
    *,
    encoding: str = "utf-8",
    include_paths: Sequence[str | Path] | None = None,
    expand_source: bool = True,
) -> RalfDocument:
    """从文件加载；若 ``expand_source`` 为真，先按 Tcl ``source`` 语义展开（含 ``include_paths`` 检索）。"""
    p = Path(path).resolve()
    text = p.read_text(encoding=encoding)
    inc = tuple(Path(x).resolve() for x in (include_paths or ()))
    line_origins: list[tuple[Path, int]] | None = None
    if expand_source:
        text, line_origins = expand_ralf_sources(
            text, current_file=p, include_paths=inc, encoding=encoding
        )
        return parse_ralf(text, line_origins=line_origins)
    return parse_ralf(text, path=p)


def loads_ralf(
    text: str,
    *,
    encoding: str = "utf-8",
    base_dir: str | Path | None = None,
    include_paths: Sequence[str | Path] | None = None,
    expand_source: bool = True,
) -> RalfDocument:
    """自字符串解析。展开 ``source`` 时相对路径相对 ``base_dir``（默认当前工作目录）。"""
    bd = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
    virtual = bd / "__inline__.ralf"
    inc = tuple(Path(x).resolve() for x in (include_paths or ()))
    if expand_source:
        text, line_origins = expand_ralf_sources(
            text,
            current_file=virtual,
            include_paths=inc,
            encoding=encoding,
        )
        return parse_ralf(text, line_origins=line_origins)
    return parse_ralf(text, path=virtual)


def dump_ralf_file(doc: RalfDocument, path: str | Path, *, encoding: str = "utf-8") -> None:
    Path(path).write_text(dump_ralf(doc), encoding=encoding)


def dumps_ralf(doc: RalfDocument) -> str:
    """序列化为字符串，等价于 `dump_ralf`。"""
    return dump_ralf(doc)

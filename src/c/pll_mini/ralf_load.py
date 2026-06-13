from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

from regmodel import Reg, RegField
from tools import run_ralfconv_flat

_PKG_DIR = Path(__file__).resolve().parent


def _resolve_ralf_path(raw: str, *, yaml_dir: Path | None) -> Path:
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    candidates: list[Path] = []
    if yaml_dir is not None:
        candidates.append(yaml_dir / path)
    candidates.append(_PKG_DIR / path)
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    raise FileNotFoundError(f"RALF 文件不存在: {raw!r}")


def load_regmodel_from_ralf(
    ralf: str,
    *,
    yaml_dir: Path | None = None,
    include_dirs: Sequence[str] = (),
    base_offset: int = 0,
) -> List[Reg]:
    """读取 RALF 并经 ralf-conv 转为 Reg 列表。"""
    ralf_path = _resolve_ralf_path(ralf, yaml_dir=yaml_dir)
    inc_paths = [Path(p) for p in include_dirs]
    text = run_ralfconv_flat(
        ralf_path,
        include_dirs=inc_paths,
        base_offset=base_offset,
    )
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError(f"ralf-conv flat JSON 须为数组，得到 {type(rows).__name__}")

    regs: List[Reg] = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("ralf-conv 数组元素须为对象")
        path = item.get("path")
        address = item.get("address")
        fields_raw = item.get("fields")
        if not isinstance(path, str) or not path:
            raise ValueError(f"寄存器项缺少 path: {item!r}")
        if not isinstance(address, int):
            raise ValueError(f"寄存器 {path!r} 的 address 须为整数")
        if not isinstance(fields_raw, list) or not fields_raw:
            raise ValueError(f"寄存器 {path!r} 的 fields 须为非空数组")
        fields: List[RegField] = []
        for fld in fields_raw:
            if not isinstance(fld, dict):
                raise ValueError(f"寄存器 {path!r} 的 field 须为对象")
            name = fld.get("name")
            lsb = fld.get("lsb")
            width = fld.get("width")
            if not isinstance(name, str) or not name:
                raise ValueError(f"寄存器 {path!r} 的 field 缺少 name")
            if not isinstance(lsb, int) or not isinstance(width, int):
                raise ValueError(
                    f"寄存器 {path!r} field {name!r} 的 lsb/width 须为整数"
                )
            fields.append(RegField(name=name, lsb=lsb, width=width))
        regs.append(Reg(path=path, address=address, fields=fields))
    return regs

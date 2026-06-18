from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOT_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)+$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")


class RegField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="field 名。")
    lsb: int = Field(..., ge=0, description="最低位索引。")
    width: int = Field(..., ge=1, le=32, description="位宽。")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _C_IDENT.match(value):
            raise ValueError(f"field name {value!r} 须为合法 C 标识符")
        return value

    @property
    def msb(self) -> int:
        return self.lsb + self.width - 1

    @property
    def mask(self) -> int:
        if self.width >= 32:
            return 0xFFFFFFFF
        return (1 << self.width) - 1

    @property
    def mask_shifted(self) -> int:
        return (self.mask << self.lsb) & 0xFFFFFFFF

    @property
    def mask_hex(self) -> str:
        return f"0x{self.mask_shifted:08X}u"

    def pack_value(self, reg_value: int, field_value: int) -> int:
        """把 field 值合并进 32 位寄存器快照。"""
        shifted = (field_value << self.lsb) & self.mask_shifted
        return (reg_value & ~self.mask_shifted) | shifted


def field_part_label(
    field: RegField,
    offset: Optional[int],
    width: Optional[int],
) -> str:
    """生成 field 切片标签，如 fbdiv 或 fbdiv[11:4]。"""
    if offset is None:
        return field.name
    eff_w = width if width is not None else 1
    eff_lsb = offset
    msb = eff_lsb + eff_w - 1
    if eff_w == 1:
        return f"{field.name}[{eff_lsb}]"
    return f"{field.name}[{msb}:{eff_lsb}]"


def pack_field_value(reg_value: int, ref: "FieldRef", field_value: int) -> int:
    """按 FieldRef 有效位域把 field 值合并进寄存器快照。"""
    lsb = ref.effective_lsb
    mask = ref.effective_mask
    shifted = (field_value << lsb) & mask
    return (reg_value & ~mask) | shifted


def path_to_macro_prefix(path: str) -> str:
    """把寄存器点分路径转为 C 宏前缀，如 blk_pll_sc.pd → BLK_PLL_SC_PD。"""
    for seg in path.split("."):
        if not _C_IDENT.match(seg):
            raise ValueError(
                f"path 段 {seg!r} 须为合法 C 标识符片段，完整 path: {path!r}"
            )
    return path.replace(".", "_").upper()


class Reg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., min_length=1, description="寄存器点分路径，并作为 C 宏前缀来源。")
    address: int = Field(..., ge=0, description="寄存器物理地址。")
    fields: List[RegField] = Field(..., min_length=1, description="field 列表。")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not _DOT_PATH.match(value):
            raise ValueError(f"reg path {value!r} 须为至少两段的点分路径")
        path_to_macro_prefix(value)
        return value

    @model_validator(mode="after")
    def _validate_fields(self) -> Reg:
        seen: set[str] = set()
        for fld in self.fields:
            if fld.name in seen:
                raise ValueError(
                    f"reg path {self.path!r} 的 fields 中 name {fld.name!r} 重复"
                )
            seen.add(fld.name)
        for i, a in enumerate(self.fields):
            for b in self.fields[i + 1 :]:
                if a.lsb + a.width <= b.lsb or b.lsb + b.width <= a.lsb:
                    continue
                raise ValueError(
                    f"reg path {self.path!r} 的 field {a.name!r} 与 {b.name!r} "
                    f"比特范围重叠"
                )
        return self

    @property
    def macro_prefix(self) -> str:
        return path_to_macro_prefix(self.path)

    @property
    def addr_macro(self) -> str:
        return f"REG_{self.macro_prefix}_ADDR"

    @property
    def address_hex(self) -> str:
        return f"0x{self.address:X}"

    def field_by_name(self, name: str) -> Optional[RegField]:
        for fld in self.fields:
            if fld.name == name:
                return fld
        return None


@dataclass(frozen=True)
class FieldRef:
    """节点 reg 路径解析结果。"""

    reg: Reg
    field: RegField
    offset: Optional[int]
    width: Optional[int]

    @property
    def effective_lsb(self) -> int:
        if self.offset is None:
            return self.field.lsb
        return self.field.lsb + self.offset

    @property
    def effective_width(self) -> int:
        if self.width is not None:
            return self.width
        if self.offset is not None:
            return 1
        return self.field.width

    @property
    def effective_mask(self) -> int:
        w = self.effective_width
        if w >= 32:
            return 0xFFFFFFFF
        return ((1 << w) - 1) << self.effective_lsb

    @property
    def lsb_macro(self) -> str:
        return f"REG_{self.reg.macro_prefix}_{self.field.name.upper()}_LSB"

    @property
    def mask_macro(self) -> str:
        return f"REG_{self.reg.macro_prefix}_{self.field.name.upper()}_MASK"


def parse_field_path(raw: str, *, ctx: str) -> Tuple[str, str, Optional[int], Optional[int]]:
    """解析节点 reg 点分路径与可选比特后缀。

    Args:
        raw: 如 blk.field 或 blk.reg.field[3:0]。
        ctx: 报错上下文。

    Returns:
        register_path, field_name, offset, width。

    Raises:
        ValueError: 路径非法或未找到 field 段时。
    """
    text = raw.strip()
    if not text:
        raise ValueError(f"{ctx} 寄存器路径不得为空")

    m = _REG_BIT_SUFFIX.search(text)
    offset: Optional[int] = None
    width: Optional[int] = None
    if m:
        body = m.group("body").strip()
        base = text[: m.start()]
        if ":" in body:
            parts = body.split(":", 1)
            try:
                msb = int(parts[0].strip(), 10)
                lsb = int(parts[1].strip(), 10)
            except ValueError as exc:
                raise ValueError(
                    f"{ctx} 比特范围 {body!r} 须为 msb:lsb 形式，完整路径: {raw!r}"
                ) from exc
            if msb < lsb:
                raise ValueError(
                    f"{ctx} 比特范围 msb {msb} 须不小于 lsb {lsb}，完整路径: {raw!r}"
                )
            offset = lsb
            width = msb - lsb + 1
        else:
            try:
                bit = int(body, 10)
            except ValueError as exc:
                raise ValueError(
                    f"{ctx} 单比特索引 {body!r} 须为十进制整数，完整路径: {raw!r}"
                ) from exc
            offset = bit
            width = 1
        text = base

    segments = text.split(".")
    if len(segments) < 2:
        raise ValueError(f"{ctx} 路径 {raw!r} 须至少含 block.field 两段")
    field_name = segments[-1]
    register_path = ".".join(segments[:-1])
    return register_path, field_name, offset, width


class RegModelIndex:
    """由 regmodel 列表建立的寄存器与 field 查找表。"""

    def __init__(self, regs: List[Reg]) -> None:
        self._regs = list(regs)
        self._by_path: Dict[str, Reg] = {}
        for reg in regs:
            if reg.path in self._by_path:
                raise ValueError(f"regmodel 中 path {reg.path!r} 重复")
            self._by_path[reg.path] = reg

    @property
    def regs(self) -> List[Reg]:
        return list(self._regs)

    def resolve(self, raw_path: str, *, ctx: str) -> FieldRef:
        register_path, field_name, offset, width = parse_field_path(raw_path, ctx=ctx)
        reg = self._by_path.get(register_path)
        if reg is None:
            raise ValueError(
                f"{ctx} 路径 {raw_path!r} 的寄存器段 {register_path!r} "
                f"不在 regmodel 中"
            )
        fld = reg.field_by_name(field_name)
        if fld is None:
            raise ValueError(
                f"{ctx} 路径 {raw_path!r} 的 field {field_name!r} "
                f"不在 reg path {reg.path!r} 的 fields 中"
            )
        ref = FieldRef(reg=reg, field=fld, offset=offset, width=width)
        if offset is not None:
            eff_w = ref.effective_width
            if offset < 0 or offset + eff_w > fld.width:
                raise ValueError(
                    f"{ctx} 路径 {raw_path!r} 的比特范围超出 field "
                    f"{field_name!r} 位宽 {fld.width}"
                )
        return ref

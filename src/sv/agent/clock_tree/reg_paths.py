from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from node.python.base import Tree

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")


@dataclass(frozen=True)
class RegPathSpec:
    path: str
    offset: Optional[int]
    width: Optional[int]


@dataclass(frozen=True)
class RegBindingRow:
    sv_access: str
    member: str
    path: str
    offset: Optional[int]
    width: Optional[int]
    node_name: str
    role: str
    alias_count: int = 1
    encoding: Optional[str] = None
    """插件提供的稳态字段编码，复位和触发字段为空。"""

    @property
    def identity(self) -> tuple[str, Optional[int], Optional[int]]:
        return self.path, self.offset, self.width


def parse_reg_path(raw: str, *, ctx: str) -> RegPathSpec:
    text = raw.strip()
    if not text:
        raise ValueError(f"{ctx} 寄存器路径不得为空")
    match = _REG_BIT_SUFFIX.search(text)
    base = text[:match.start()] if match else text
    if not base or any(not _SV_ID.match(part) for part in base.split(".")):
        raise ValueError(f"{ctx} 寄存器路径 {raw!r} 须为合法层次 SystemVerilog 名字")
    if not match:
        return RegPathSpec(base, None, None)
    body = match.group("body").strip()
    try:
        if ":" in body:
            msb_text, lsb_text = body.split(":", 1)
            msb, lsb = int(msb_text), int(lsb_text)
            if lsb < 0 or msb < lsb:
                raise ValueError
            return RegPathSpec(base, lsb, msb - lsb + 1)
        bit = int(body)
        if bit < 0:
            raise ValueError
        return RegPathSpec(base, bit, 1)
    except ValueError as exc:
        raise ValueError(f"{ctx} 寄存器切片 {body!r} 非法") from exc


def any_reg_configured(tree: Tree) -> bool:
    return any(
        node.regs_for_output("") or any(node.output_regs.values())
        for node in tree.nodes_ordered
    )


def analyze_reg_bindings(tree: Tree) -> tuple[List[RegBindingRow], list[tuple[str, str]]]:
    """整理寄存器绑定，并约束共享字段的编码一致。

    Args:
        tree: 已完成节点插件校验的时钟树

    Returns:
        tuple: 带别名数量的绑定列表，以及共享编码的等式两端

    Raises:
        ValueError: 路径无效、切片重叠或共享字段缺少编码定义
    """
    rows: List[RegBindingRow] = []
    for node in tree.nodes_ordered:
        for output in node.output_groups or [""]:
            access = f'{node.name}["{output}"]' if output else node.name
            for key, raw_path in sorted(node.regs_for_output(output).items()):
                if not _SV_ID.match(key):
                    raise ValueError(f"节点 {node.name!r} 的 regs 键 {key!r} 须为合法 SystemVerilog 名字")
                spec = parse_reg_path(raw_path, ctx=f"节点 {node.name!r} regs[{key!r}]")
                rows.append(RegBindingRow(access, f"f_{key}", spec.path, spec.offset, spec.width,
                    node.name, key, encoding=node.register_encoding(output, key, access)))
    groups: dict[tuple[str, Optional[int], Optional[int]], list[RegBindingRow]] = {}
    by_path: dict[str, list[RegBindingRow]] = {}
    for row in rows:
        groups.setdefault(row.identity, []).append(row)
        by_path.setdefault(row.path, []).append(row)
    for path_rows in by_path.values():
        for index, lhs in enumerate(path_rows):
            for rhs in path_rows[index + 1:]:
                if lhs.identity == rhs.identity:
                    continue
                if lhs.width is None or rhs.width is None:
                    raise ValueError(f"寄存器字段 {lhs.path} 存在重叠切片: {lhs.node_name}.{lhs.member} 与 {rhs.node_name}.{rhs.member}")
                lhs_hi = lhs.offset + lhs.width - 1
                rhs_hi = rhs.offset + rhs.width - 1
                if lhs.offset <= rhs_hi and rhs.offset <= lhs_hi:
                    raise ValueError(f"寄存器字段 {lhs.path} 存在重叠切片: {lhs.node_name}.{lhs.member} 与 {rhs.node_name}.{rhs.member}")
    constraints: list[tuple[str, str]] = []
    for group in groups.values():
        encoded = [row.encoding for row in group if row.encoding is not None]
        if encoded and len(encoded) != len(group):
            raise ValueError(f"共享字段 {group[0].path!r} 的部分节点没有提供寄存器编码")
        if len(encoded) > 1:
            anchor = encoded[0]
            constraints.extend((anchor, value) for value in encoded[1:] if value != anchor)
    return [RegBindingRow(row.sv_access, row.member, row.path, row.offset, row.width,
        row.node_name, row.role, len(groups[row.identity]), row.encoding) for row in rows], constraints

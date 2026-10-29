from __future__ import annotations
import re
from typing import Dict, List, Union
from pydantic import ValidationInfo

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]
_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REG_KEY_BRACKET = re.compile(r"\[([^\]]*)\]")


def node_output_groups(node: object) -> List[str]:
    return list(getattr(node, "output_groups", []))


def node_output_count(node: object) -> int:
    groups = node_output_groups(node)
    if groups:
        return len(groups)
    return 1


def primary_output_group(node: object) -> str:
    groups = node_output_groups(node)
    return groups[0] if groups else ""


def reg_key_to_c_ident(key: str) -> str:
    """把 YAML 逻辑 reg 键转为合法 C 名字，如 postdiv1[0] → postdiv1_0。"""
    text = _REG_KEY_BRACKET.sub(r"_\1", key)
    if text and text[0].isdigit():
        text = f"reg_{text}"
    if not _C_IDENT.match(text):
        raise ValueError(f"reg 键 {key!r} 无法转为合法 C 名字，得到 {text!r}")
    return text


def validate_reg_path(path: str, *, ctx: str) -> None:
    from load.regmodel import parse_field_path

    parse_field_path(path, ctx=ctx)


def validate_optional_reg(path: str, *, node_name: str, kind: str) -> None:
    if path:
        validate_reg_path(path, ctx=f"{kind} 节点 {node_name!r} reg")


def flatten_regs(regs: RegsMap) -> dict[str, str]:
    flat: dict[str, str] = {}
    for blk, val in regs.items():
        if not _SV_ID.match(blk):
            raise ValueError(f"regs 键 {blk!r} 须为合法 SystemVerilog 名字")
        if isinstance(val, str):
            validate_reg_path(val, ctx=f"regs[{blk!r}]")
            flat[blk] = val
        else:
            for field, tail in val.items():
                if not _SV_ID.match(field):
                    raise ValueError(
                        f"regs[{blk!r}] 内键 {field!r} 须为合法 SystemVerilog 名字"
                    )
                full = f"{blk}.{tail}"
                validate_reg_path(full, ctx=f"regs[{blk!r}][{field!r}]")
                flat[field] = full
    return flat


def validate_regs_exact(
    regs: dict[str, str],
    allowed: frozenset[str],
    *,
    node_name: str,
    kind: str,
) -> None:
    if not regs:
        return
    got = set(regs.keys())
    if got != allowed:
        missing = sorted(allowed - got)
        extra = sorted(got - allowed)
        parts: list[str] = []
        if missing:
            parts.append(f"缺少 {missing}")
        if extra:
            parts.append(f"多余 {extra}")
        raise ValueError(
            f"{kind} 节点 {node_name!r} 的 regs 键须与允许集合完全一致"
            f"（{'; '.join(parts)}）；允许 {sorted(allowed)}"
        )
    for key, path in regs.items():
        validate_reg_path(path, ctx=f"{kind} 节点 {node_name!r} regs[{key!r}]")


def _validation_node_name(node: object, info: ValidationInfo) -> str:
    key = (info.context or {}).get("node_name")
    if isinstance(key, str) and key:
        return key
    name = getattr(node, "_name", "")
    if name:
        return name
    raise ValueError("节点须在 Tree.nodes 字典键上下文内校验")

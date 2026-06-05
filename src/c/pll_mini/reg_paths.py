from __future__ import annotations

import re
from typing import Dict, List, Optional, Union

from pydantic import ValidationInfo

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux"})

DIV_REG_KEYS = frozenset({"rst", "load", "div"})

DTO_REG_KEYS = frozenset({"rst", "load", "bypass", "step"})

_PLL_KIND_CANON = frozenset({"tci", "sc", "dw", "inno"})

INNO_PLL_SHARED_REG_KEYS = frozenset({"lock", "pd", "refdiv", "fbdiv"})

PLL_KIND_TO_SV: dict[str, str] = {
    "tci": "pll_tci",
    "sc": "pll_sc",
    "dw": "pll_dw",
    "inno": "pll_inno",
}

PLL_REG_KEYS: dict[str, frozenset[str]] = {
    "tci": frozenset({
        "lock",
        "bypass",
        "pwrdn",
        "reset",
        "clkod",
        "clkf",
        "clkr",
        "bwadj",
    }),
    "sc": frozenset({
        "lock",
        "vocpd",
        "postdivpd",
        "dsmpd",
        "pd",
        "bypass",
        "refdiv",
        "postdiv2",
        "postdiv1",
        "fbdiv",
    }),
    "dw": frozenset({
        "lock",
        "fbdiv",
        "prediv",
        "reset",
        "pwron",
        "shift",
        "bypass",
        "divvcor",
        "r",
        "p",
        "divvcop",
        "enr",
        "enp",
    }),
    "inno": frozenset({
        "lock",
        "pd",
        "postdiv1",
        "refdiv",
        "postdiv2",
        "fbdiv",
    }),
}


def inno_pll_reg_keys(output_count: int) -> frozenset[str]:
    keys = set(INNO_PLL_SHARED_REG_KEYS)
    for idx in range(output_count):
        if idx == 0:
            keys.add("postdiv1")
            keys.add("postdiv2")
        else:
            keys.add(f"postdiv1_{idx}")
            keys.add(f"postdiv2_{idx}")
    return frozenset(keys)


def inno_postdiv_reg_keys(group_id: int) -> tuple[str, str]:
    if group_id == 0:
        return "postdiv1", "postdiv2"
    return f"postdiv1_{group_id}", f"postdiv2_{group_id}"


def normalize_pll_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"pll_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _PLL_KIND_CANON:
        raise ValueError(
            f"pll_kind 须为 tci、sc、dw、inno 之一，大小写不限，得到 {value!r}"
        )
    return canon


def validate_reg_path(path: str, *, ctx: str) -> None:
    from regmodel import parse_field_path

    parse_field_path(path, ctx=ctx)


def validate_optional_reg(path: str, *, node_name: str, kind: str) -> None:
    if path:
        validate_reg_path(path, ctx=f"{kind} 节点 {node_name!r} reg")


def flatten_regs(regs: RegsMap) -> dict[str, str]:
    flat: dict[str, str] = {}
    for blk, val in regs.items():
        if not _SV_ID.match(blk):
            raise ValueError(f"regs 键 {blk!r} 须为合法 SystemVerilog 标识符")
        if isinstance(val, str):
            validate_reg_path(val, ctx=f"regs[{blk!r}]")
            flat[blk] = val
        else:
            for field, tail in val.items():
                if not _SV_ID.match(field):
                    raise ValueError(
                        f"regs[{blk!r}] 内键 {field!r} 须为合法 SystemVerilog 标识符"
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


def validate_pll_regs_exact(
    regs: dict[str, str],
    pll_kind: str,
    *,
    node_name: str,
    output_count: int = 1,
) -> None:
    if pll_kind == "inno" and output_count > 1:
        allowed = inno_pll_reg_keys(output_count)
    else:
        allowed = PLL_REG_KEYS.get(pll_kind)
        if output_count > 1:
            raise ValueError(
                f"pll 节点 {node_name!r} output_count 为 {output_count} 时 pll_kind 须为 inno"
            )
    if allowed is None:
        raise ValueError(f"pll 节点 {node_name!r} 未知 pll_kind {pll_kind!r}")
    validate_regs_exact(regs, allowed, node_name=node_name, kind=f"pll({pll_kind})")


def _validation_node_name(node: object, info: ValidationInfo) -> str:
    key = (info.context or {}).get("node_name")
    if isinstance(key, str) and key:
        return key
    name = getattr(node, "_name", "")
    if name:
        return name
    raise ValueError("节点须在 Tree.nodes 字典键上下文内校验")

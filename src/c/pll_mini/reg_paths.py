from __future__ import annotations

import re
from typing import Dict, List, Optional, Union

from pydantic import ValidationInfo

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REG_KEY_BRACKET = re.compile(r"\[([^\]]*)\]")

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux"})

DIV_REG_KEYS = frozenset({"rst", "load", "div"})

DTO_REG_KEYS = frozenset({"rst", "load", "bypass", "step"})

CPU_GATE_REG_KEYS = frozenset({"rst", "div"})

CPU_GATE_OUTPUT_GROUPS: tuple[str, ...] = ("hclk_en", "hclk", "clk_arm_core")

_DIV_KIND_CANON = frozenset({"div", "div_n", "dto", "dto_n", "cpu_gate", "div_r"})

_SOURCE_KIND_CANON = frozenset({"source", "pad", "vdd", "gnd"})
_FIXED_ZERO_FREQ_SOURCE_KINDS = frozenset({"vdd", "gnd"})

_PLL_KIND_CANON = frozenset({"tci", "sc", "dw", "inno"})

INNO_PLL_SHARED_REG_KEYS = frozenset({"lock", "pd", "refdiv", "fbdiv"})

INNO_PLL_OUTPUT_GROUPS = ["0", "1"]

_INV_KIND_CANON = frozenset({"inv", "mux_inv", "inv_cell"})

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


def node_output_groups(node: object) -> List[str]:
    kind = getattr(node, "kind", None)
    if kind == "pll":
        return list(getattr(node, "output_groups", []))
    if kind == "div" and getattr(node, "div_kind", None) == "cpu_gate":
        return list(CPU_GATE_OUTPUT_GROUPS)
    return []


def node_output_count(node: object) -> int:
    groups = node_output_groups(node)
    if groups:
        return len(groups)
    return 1


def primary_output_group(node: object) -> str:
    groups = node_output_groups(node)
    return groups[0] if groups else ""


def normalize_div_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"div_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _DIV_KIND_CANON:
        raise ValueError(
            f"div_kind 须为 div、div_n、dto、dto_n、cpu_gate、div_r 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def normalize_source_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"source_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _SOURCE_KIND_CANON:
        raise ValueError(
            f"source_kind 须为 source、pad、vdd、gnd 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def div_reg_keys_for_kind(div_kind: str) -> frozenset[str]:
    if div_kind in ("div", "div_n"):
        return DIV_REG_KEYS
    if div_kind == "cpu_gate":
        return CPU_GATE_REG_KEYS
    if div_kind == "div_r":
        return frozenset()
    return DTO_REG_KEYS


def div_kind_uses_div_regs(div_kind: str) -> bool:
    return div_kind in ("div", "div_n")


def inno_pll_reg_keys() -> frozenset[str]:
    keys = set(INNO_PLL_SHARED_REG_KEYS)
    for group_id in INNO_PLL_OUTPUT_GROUPS:
        keys.add(f"postdiv1[{group_id}]")
        keys.add(f"postdiv2[{group_id}]")
    return frozenset(keys)


def inno_postdiv_reg_keys(group_id: str) -> tuple[str, str]:
    return f"postdiv1[{group_id}]", f"postdiv2[{group_id}]"


def reg_key_to_c_ident(key: str) -> str:
    """把 YAML 逻辑 reg 键转为合法 C 名字，如 postdiv1[0] → postdiv1_0。"""
    text = _REG_KEY_BRACKET.sub(r"_\1", key)
    if text and text[0].isdigit():
        text = f"reg_{text}"
    if not _C_IDENT.match(text):
        raise ValueError(
            f"reg 键 {key!r} 无法转为合法 C 名字，得到 {text!r}"
        )
    return text


def normalize_inv_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"inv_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _INV_KIND_CANON:
        raise ValueError(
            f"inv_kind 须为 inv、mux_inv、inv_cell 之一，大小写不限，得到 {value!r}"
        )
    return canon


def normalize_cell_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"cell_kind 应为字符串，得到 {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"cell_kind 应为非空字符串，得到 {value!r}")
    return text


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


def validate_pll_regs_exact(
    regs: dict[str, str],
    pll_kind: str,
    *,
    node_name: str,
    output_groups: Optional[List[str]] = None,
) -> None:
    groups = output_groups or []
    if pll_kind == "inno":
        allowed = inno_pll_reg_keys()
    else:
        allowed = PLL_REG_KEYS.get(pll_kind)
        if groups:
            raise ValueError(
                f"pll 节点 {node_name!r} 配置了多路输出时 pll_kind 须为 inno"
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

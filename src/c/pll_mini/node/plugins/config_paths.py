from __future__ import annotations

import re
from typing import Dict, List, Optional, Union

from reg_paths import validate_regs_exact

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REG_KEY_BRACKET = re.compile(r"\[([^\]]*)\]")

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux"})

DIV_REG_KEYS = frozenset({"rst", "load", "div"})

DTO_REG_KEYS = frozenset({"rst", "load", "bypass", "step"})

_DIV_KIND_CANON = frozenset({"div", "div_n", "dto", "dto_n", "div_r"})

_SOURCE_KIND_CANON = frozenset({"source", "pad"})

_PLL_KIND_CANON = frozenset({"tci", "sc", "dw", "inno"})

INNO_PLL_SHARED_REG_KEYS = frozenset({"lock", "pd", "refdiv", "fbdiv"})

INNO_PLL_OUTPUT_GROUPS = ["0", "1"]

_INV_KIND_CANON = frozenset({"inv", "inv_mux", "inv_cell"})

PLL_KIND_TO_SV: dict[str, str] = {
    "tci": "pll_tci",
    "sc": "pll_sc",
    "dw": "pll_dw",
    "inno": "pll_inno",
}

PLL_REG_KEYS: dict[str, frozenset[str]] = {
    "tci": frozenset(
        {
            "lock",
            "bypass",
            "pwrdn",
            "reset",
            "clkod",
            "clkf",
            "clkr",
            "bwadj",
        }
    ),
    "sc": frozenset(
        {
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
        }
    ),
    "dw": frozenset(
        {
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
        }
    ),
    "inno": frozenset(
        {
            "lock",
            "pd",
            "postdiv1",
            "refdiv",
            "postdiv2",
            "fbdiv",
        }
    ),
}


def normalize_div_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"div_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _DIV_KIND_CANON:
        raise ValueError(
            f"div_kind 须为 div、div_n、dto、dto_n、div_r 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def normalize_source_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"source_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _SOURCE_KIND_CANON:
        raise ValueError(
            f"source_kind 须为 source、pad 之一，大小写不限，得到 {value!r}"
        )
    return canon


def div_reg_keys_for_kind(div_kind: str) -> frozenset[str]:
    if div_kind in ("div", "div_n"):
        return DIV_REG_KEYS
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


def normalize_inv_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"inv_kind 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _INV_KIND_CANON:
        raise ValueError(
            f"inv_kind 须为 inv、inv_mux、inv_cell 之一，大小写不限，得到 {value!r}"
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

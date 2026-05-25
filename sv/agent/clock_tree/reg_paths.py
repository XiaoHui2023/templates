from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List, Union

if TYPE_CHECKING:
    from sv.agent.clock_tree.nodes import Tree

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

DIV_REG_KEYS = frozenset({"ratio", "enable", "bypass"})
DTO_REG_KEYS = frozenset({"ratio", "duty", "enable", "bypass"})

PLL_REG_KEYS: dict[str, frozenset[str]] = {
    "PLL_TCI": frozenset({"lock", "bypass", "ndiv", "fdiv", "pd"}),
    "PLL_SC": frozenset({"lock", "en", "mult"}),
    "PLL_DW": frozenset({"lock", "pwdn", "m", "n", "od"}),
}


def validate_reg_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} 寄存器路径不得为空")
    for seg in path.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(
                f"{ctx} 路径段 {seg!r} 须为合法 SystemVerilog 标识符，完整路径: {path!r}"
            )


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
                if not _SV_ID.match(tail):
                    raise ValueError(
                        f"regs[{blk!r}][{field!r}] 尾段 {tail!r} "
                        f"须为合法 SystemVerilog 标识符"
                    )
                full = f"{blk}.{tail}"
                validate_reg_path(full, ctx=f"regs[{blk!r}][{field!r}]")
                flat[field] = full
    return flat


def validate_regs_against_allowed(
    regs: RegsMap,
    allowed: frozenset[str],
    *,
    node_name: str,
    kind: str,
) -> None:
    flat = flatten_regs(regs)
    unknown = set(flat) - allowed
    if unknown:
        raise ValueError(
            f"{kind} 节点 {node_name!r} 的 regs 含未知逻辑名 {sorted(unknown)}；"
            f"允许: {sorted(allowed)}"
        )


def reg_path_sv_expr(path: str, root: str = "regmodel") -> str:
    return f"{root}.{path}"


def collect_div_reg_keys(trees: List[Tree]) -> List[str]:
    return []


def collect_dto_reg_keys(trees: List[Tree]) -> List[str]:
    return []


def collect_pll_reg_keys(trees: List[Tree]) -> List[str]:
    return []


def any_gate_reg_configured(trees: List[Tree]) -> bool:
    return False


def any_reg_configured(trees: List[Tree]) -> bool:
    return False


def iter_reg_bindings(trees: List[Tree]) -> List[tuple[str, str, str, str]]:
    return []

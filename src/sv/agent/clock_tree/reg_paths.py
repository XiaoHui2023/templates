from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List, Union

if TYPE_CHECKING:
    from nodes import Tree

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux", "div"})

DTO_REG_KEYS = frozenset({"rstn", "load", "bypass", "step"})

PLL_REG_KEYS: dict[str, frozenset[str]] = {
    "PLL_TCI": frozenset({
        "lock",
        "bypass",
        "pwrdn",
        "reset",
        "clkod",
        "clkf",
        "clkr",
        "bwadj",
    }),
    "PLL_SC": frozenset({
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
    "PLL_DW": frozenset({
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
}

PLL_KIND_TO_SV: dict[str, str] = {
    "PLL_TCI": "pll_tci",
    "PLL_SC": "pll_sc",
    "PLL_DW": "pll_dw",
}


def validate_reg_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} 寄存器路径不得为空")
    for seg in path.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(
                f"{ctx} 路径段 {seg!r} 须为合法 SystemVerilog 标识符，完整路径: {path!r}"
            )


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
                if not _SV_ID.match(tail):
                    raise ValueError(
                        f"regs[{blk!r}][{field!r}] 尾段 {tail!r} "
                        f"须为合法 SystemVerilog 标识符"
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
) -> None:
    allowed = PLL_REG_KEYS.get(pll_kind)
    if allowed is None:
        raise ValueError(f"pll 节点 {node_name!r} 未知 pll_kind {pll_kind!r}")
    validate_regs_exact(regs, allowed, node_name=node_name, kind=f"pll({pll_kind})")


def reg_path_sv_expr(path: str, root: str = "regmodel") -> str:
    return f"{root}.{path}"


def collect_pll_sv_classes(trees: List[Tree]) -> List[str]:
    kinds: set[str] = set()
    for tree in trees:
        for node in tree.nodes_ordered:
            if node.kind != "pll":
                continue
            kinds.add(PLL_KIND_TO_SV[node.pll_kind])
    return sorted(kinds)


def _node_reg_configured(node: object) -> bool:
    if getattr(node, "kind", None) in SINGLE_REG_NODE_KINDS:
        return bool(getattr(node, "reg", ""))
    regs = getattr(node, "regs", None)
    return bool(regs)


def any_reg_configured(trees: List[Tree]) -> bool:
    for tree in trees:
        for node in tree.nodes_ordered:
            if _node_reg_configured(node):
                return True
    return False


def iter_reg_bindings(trees: List[Tree]) -> List[tuple[str, str, str, str]]:
    out: List[tuple[str, str, str, str]] = []
    for tree in trees:
        for node in tree.nodes_ordered:
            if not _node_reg_configured(node):
                continue
            if node.kind in SINGLE_REG_NODE_KINDS:
                validate_optional_reg(node.reg, node_name=node.name, kind=node.kind)
                out.append((tree.name, node.name, "f_reg", node.reg))
            elif node.kind == "pll":
                validate_pll_regs_exact(
                    node.regs, node.pll_kind, node_name=node.name
                )
                for key, path in sorted(node.regs.items()):
                    out.append((tree.name, node.name, f"f_{key}", path))
            elif node.kind == "dto":
                validate_regs_exact(
                    node.regs,
                    DTO_REG_KEYS,
                    node_name=node.name,
                    kind="dto",
                )
                for key, path in sorted(node.regs.items()):
                    out.append((tree.name, node.name, f"f_{key}", path))
            else:
                flat = flatten_regs(node.regs)
                for key, path in sorted(flat.items()):
                    out.append((tree.name, node.name, f"f_{key}", path))
    return out

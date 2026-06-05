from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Union

if TYPE_CHECKING:
    from nodes import Tree


def node_output_count(node: object) -> int:
    if getattr(node, "kind", None) == "pll":
        return int(getattr(node, "output_count", 1))
    return 1


def sv_node_access(node_key: str, group_id: int, output_count: int) -> str:
    if output_count <= 1:
        return node_key
    return f"{node_key}[{group_id}]"

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux"})

DIV_REG_KEYS = frozenset({"rst", "load", "div"})

DTO_REG_KEYS = frozenset({"rst", "load", "bypass", "step"})

_PLL_KIND_CANON = frozenset({"tci", "sc", "dw", "inno"})

INNO_PLL_SHARED_REG_KEYS = frozenset({"lock", "pd", "refdiv", "fbdiv"})

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

PLL_KIND_TO_SV: dict[str, str] = {
    "tci": "pll_tci",
    "sc": "pll_sc",
    "dw": "pll_dw",
    "inno": "pll_inno",
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


@dataclass(frozen=True)
class RegPathSpec:
    """寄存器模型点分路径与 field 内比特切片；width/offset 为 None 时在 SV 绑定时取整域 field。"""

    path: str
    offset: Optional[int]
    width: Optional[int]


RegBindingRow = tuple[str, str, str, str, Optional[int], Optional[int]]


def _validate_dot_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} 寄存器路径不得为空")
    for seg in path.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(
                f"{ctx} 路径段 {seg!r} 须为合法 SystemVerilog 标识符，完整路径: {path!r}"
            )


def parse_reg_path(raw: str, *, ctx: str) -> RegPathSpec:
    raw = raw.strip()
    if not raw:
        raise ValueError(f"{ctx} 寄存器路径不得为空")

    m = _REG_BIT_SUFFIX.search(raw)
    if not m:
        _validate_dot_path(raw, ctx=ctx)
        return RegPathSpec(path=raw, offset=None, width=None)

    base = raw[: m.start()]
    _validate_dot_path(base, ctx=ctx)

    body = m.group("body").strip()
    if ":" in body:
        parts = body.split(":", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValueError(
                f"{ctx} 比特范围 {body!r} 须为 msb:lsb 形式，完整路径: {raw!r}"
            )
        try:
            msb = int(parts[0].strip(), 10)
            lsb = int(parts[1].strip(), 10)
        except ValueError as exc:
            raise ValueError(
                f"{ctx} 比特范围 {body!r} 须为十进制整数，完整路径: {raw!r}"
            ) from exc
        if msb < lsb:
            raise ValueError(
                f"{ctx} 比特范围 msb {msb} 须不小于 lsb {lsb}，完整路径: {raw!r}"
            )
        if lsb < 0:
            raise ValueError(f"{ctx} lsb 须非负，完整路径: {raw!r}")
        return RegPathSpec(path=base, offset=lsb, width=msb - lsb + 1)

    try:
        bit = int(body, 10)
    except ValueError as exc:
        raise ValueError(
            f"{ctx} 单比特索引 {body!r} 须为十进制整数，完整路径: {raw!r}"
        ) from exc
    if bit < 0:
        raise ValueError(f"{ctx} 单比特索引须非负，完整路径: {raw!r}")
    return RegPathSpec(path=base, offset=bit, width=1)


def validate_reg_path(path: str, *, ctx: str) -> None:
    parse_reg_path(path, ctx=ctx)


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


def reg_path_sv_expr(path: str, root: str = "regmodel") -> str:
    spec = parse_reg_path(path, ctx="reg_path_sv_expr")
    return f"{root}.{spec.path}"


def collect_pll_sv_classes(tree: Tree) -> List[str]:
    kinds: set[str] = set()
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


def any_reg_configured(tree: Tree) -> bool:
    for node in tree.nodes_ordered:
        if _node_reg_configured(node):
            return True
    return False


def any_node_path(tree: Tree) -> bool:
    """任一节点配置了非空 RTL path 时为真，用于决定是否展开 interface 与 tree_connection。"""
    for node in tree.nodes_ordered:
        if node.path:
            return True
    return False


def node_has_path_and_reg(node: object) -> bool:
    """节点同时配置了非空 path 与 reg 或 regs 时为真。"""
    if not getattr(node, "path", ""):
        return False
    return _node_reg_configured(node)


def any_node_path_and_reg(tree: Tree) -> bool:
    """任一节点同时配置 path 与 reg(regs) 时为真，用于 enable_node_fix。"""
    for node in tree.nodes_ordered:
        if node_has_path_and_reg(node):
            return True
    return False


def _append_binding(
    out: List[RegBindingRow],
    tree_name: str,
    sv_access: str,
    member: str,
    raw_path: str,
) -> None:
    spec = parse_reg_path(
        raw_path,
        ctx=f"tree {tree_name!r} access {sv_access!r} member {member!r}",
    )
    out.append((tree_name, sv_access, member, spec.path, spec.offset, spec.width))


def _pll_reg_bindings(
    out: List[RegBindingRow],
    tree: Tree,
    node: object,
) -> None:
    assert node.kind == "pll"
    count = node_output_count(node)
    regs: dict[str, str] = node.regs
    validate_pll_regs_exact(
        regs,
        node.pll_kind,
        node_name=node.name,
        output_count=count,
    )
    if node.pll_kind == "inno" and count > 1:
        for group_id in range(count):
            access = sv_node_access(node.name, group_id, count)
            for key in sorted(INNO_PLL_SHARED_REG_KEYS):
                _append_binding(
                    out, tree.name, access, f"f_{key}", regs[key]
                )
            p1_key, p2_key = inno_postdiv_reg_keys(group_id)
            _append_binding(
                out, tree.name, access, "f_postdiv1", regs[p1_key]
            )
            _append_binding(
                out, tree.name, access, "f_postdiv2", regs[p2_key]
            )
        return
    access = sv_node_access(node.name, 0, count)
    for key, path in sorted(regs.items()):
        _append_binding(out, tree.name, access, f"f_{key}", path)


def iter_reg_bindings(tree: Tree) -> List[RegBindingRow]:
    out: List[RegBindingRow] = []
    for node in tree.nodes_ordered:
        if not _node_reg_configured(node):
            continue
        if node.kind in SINGLE_REG_NODE_KINDS:
            validate_optional_reg(node.reg, node_name=node.name, kind=node.kind)
            access = sv_node_access(node.name, 0, node_output_count(node))
            _append_binding(out, tree.name, access, "f_reg", node.reg)
        elif node.kind == "pll":
            _pll_reg_bindings(out, tree, node)
        elif node.kind == "div":
            validate_regs_exact(
                node.regs,
                DIV_REG_KEYS,
                node_name=node.name,
                kind="div",
            )
            access = sv_node_access(node.name, 0, node_output_count(node))
            for key, path in sorted(node.regs.items()):
                _append_binding(out, tree.name, access, f"f_{key}", path)
        elif node.kind == "dto":
            validate_regs_exact(
                node.regs,
                DTO_REG_KEYS,
                node_name=node.name,
                kind="dto",
            )
            access = sv_node_access(node.name, 0, node_output_count(node))
            for key, path in sorted(node.regs.items()):
                _append_binding(out, tree.name, access, f"f_{key}", path)
        else:
            flat = flatten_regs(node.regs)
            access = sv_node_access(node.name, 0, node_output_count(node))
            for key, path in sorted(flat.items()):
                _append_binding(out, tree.name, access, f"f_{key}", path)
    return out

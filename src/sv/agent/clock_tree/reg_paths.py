from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Union

if TYPE_CHECKING:
    from nodes import Tree

from schema_error import ERR


def node_output_groups(node: object) -> List[str]:
    kind = getattr(node, "kind", None)
    if kind == "pll":
        return list(getattr(node, "output_groups", []))
    return []


def node_output_count(node: object) -> int:
    groups = node_output_groups(node)
    if groups:
        return len(groups)
    return 1


def primary_output_group(node: object) -> str:
    groups = node_output_groups(node)
    return groups[0] if groups else ""


def sv_node_access(node_key: str, group_id: str, groups: List[str]) -> str:
    if not groups:
        return node_key
    return f'{node_key}["{group_id}"]'

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")

RegPathGroup = Dict[str, str]
RegsMap = Dict[str, Union[str, RegPathGroup]]

SINGLE_REG_NODE_KINDS = frozenset({"gate", "mux", "inv"})

DIV_REG_KEYS = frozenset({"rst", "load", "div"})

DTO_REG_KEYS = frozenset({"rst", "load", "bypass", "step"})

_DIV_KIND_CANON = frozenset({"div", "dto", "div_r"})

_INV_KIND_CANON = frozenset({"inv", "inv_mux", "inv_cell"})

DIV_KIND_TO_SV: dict[str, str] = {
    "div": "div_div",
    "dto": "div_dto",
    "div_r": "div_div_r",
}

DIV_KIND_TO_SV_ENUM: dict[str, str] = {
    "div": "DIV",
    "dto": "DTO",
    "div_r": "DIV_R",
}

INV_KIND_TO_SV: dict[str, str] = {
    "inv": "inv",
    "inv_mux": "inv_mux",
    "inv_cell": "inv_cell",
}

_SOURCE_KIND_CANON = frozenset({"source", "pad"})

SOURCE_KIND_TO_SV: dict[str, str] = {
    "source": "source",
    "pad": "source_pad",
}

SOURCE_KIND_TO_SV_ENUM: dict[str, str] = {
    "source": "SOURCE",
    "pad": "PAD",
}

INV_KIND_TO_SV_ENUM: dict[str, str] = {
    "inv": "INV",
    "inv_mux": "INV_MUX",
    "inv_cell": "INV_CELL",
}


def normalize_div_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ERR.field('div_kind')} 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _DIV_KIND_CANON:
        raise ValueError(
            f"{ERR.field('div_kind')} 须为 div、dto、div_r 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def normalize_inv_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ERR.field('inv_kind')} 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _INV_KIND_CANON:
        raise ValueError(
            f"{ERR.field('inv_kind')} 须为 inv、inv_mux、inv_cell 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def normalize_cell_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ERR.field('cell_kind')} 应为字符串，得到 {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"{ERR.field('cell_kind')} 应为非空字符串，得到 {value!r}")
    return text


def normalize_source_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ERR.field('source_kind')} 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _SOURCE_KIND_CANON:
        raise ValueError(
            f"{ERR.field('source_kind')} 须为 source、pad 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


def div_reg_keys_for_kind(div_kind: str) -> frozenset[str]:
    if div_kind == "div":
        return DIV_REG_KEYS
    if div_kind == "div_r":
        return frozenset()
    return DTO_REG_KEYS


def div_kind_uses_div_regs(div_kind: str) -> bool:
    return div_kind == "div"

_PLL_KIND_CANON = frozenset({"tci", "sc", "dw", "inno"})

INNO_PLL_SHARED_REG_KEYS = frozenset({"lock", "pd", "refdiv", "fbdiv"})

INNO_PLL_OUTPUT_GROUPS = ["0", "1"]

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


def inno_pll_reg_keys() -> frozenset[str]:
    keys = set(INNO_PLL_SHARED_REG_KEYS)
    for group_id in INNO_PLL_OUTPUT_GROUPS:
        keys.add(f"postdiv1[{group_id}]")
        keys.add(f"postdiv2[{group_id}]")
    return frozenset(keys)


def inno_postdiv_reg_keys(group_id: str) -> tuple[str, str]:
    return f"postdiv1[{group_id}]", f"postdiv2[{group_id}]"


def normalize_pll_kind(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ERR.field('pll_kind')} 须为字符串，得到 {type(value).__name__}")
    canon = value.strip().lower()
    if canon not in _PLL_KIND_CANON:
        raise ValueError(
            f"{ERR.field('pll_kind')} 须为 tci、sc、dw、inno 之一，"
            f"大小写不限，得到 {value!r}"
        )
    return canon


@dataclass(frozen=True)
class RegPathSpec:
    """寄存器模型路径，按 `.` 分隔，与 field 内比特切片；width/offset 为 None 时在 SV 绑定时取整域 field。"""

    path: str
    offset: Optional[int]
    width: Optional[int]


RegBindingRow = tuple[str, str, str, Optional[int], Optional[int]]


def _validate_dot_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} 寄存器路径不得为空")
    for seg in path.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(
                f"{ctx} 路径段 {seg!r} 须为合法 SystemVerilog 名字，完整路径: {path!r}"
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
        validate_reg_path(path, ctx=f"{ERR.node(kind, node_name)} {ERR.field('reg')}")


def flatten_regs(regs: RegsMap) -> dict[str, str]:
    flat: dict[str, str] = {}
    for blk, val in regs.items():
        if not _SV_ID.match(blk):
            raise ValueError(f"{ERR.field('regs')} 键 {blk!r} 须为合法 SystemVerilog 名字")
        if isinstance(val, str):
            validate_reg_path(val, ctx=f"{ERR.field('regs')}[{blk!r}]")
            flat[blk] = val
        else:
            for field, tail in val.items():
                if not _SV_ID.match(field):
                    raise ValueError(
                        f"{ERR.field('regs')}[{blk!r}] 内键 {field!r} "
                        f"须为合法 SystemVerilog 名字"
                    )
                full = f"{blk}.{tail}"
                validate_reg_path(full, ctx=f"{ERR.field('regs')}[{blk!r}][{field!r}]")
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
            f"{ERR.node(kind, node_name)} 的 {ERR.field('regs')} 键须与允许集合完全一致"
            f"（{'; '.join(parts)}）；允许 {sorted(allowed)}"
        )
    for key, path in regs.items():
        validate_reg_path(
            path,
            ctx=f"{ERR.node(kind, node_name)} {ERR.field('regs')}[{key!r}]",
        )


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
                f"{ERR.node('pll', node_name)} 配置了多路输出时 "
                f"{ERR.field('pll_kind')} 须为 'inno'"
            )
    if allowed is None:
        raise ValueError(
            f"{ERR.node('pll', node_name)} 未知 {ERR.field('pll_kind')} {pll_kind!r}"
        )
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


def collect_div_sv_classes(tree: Tree) -> List[str]:
    kinds: set[str] = set()
    for node in tree.nodes_ordered:
        if node.kind != "div":
            continue
        kinds.add(DIV_KIND_TO_SV[node.div_kind])
    return sorted(kinds)


def collect_inv_sv_classes(tree: Tree) -> List[str]:
    kinds: set[str] = set()
    for node in tree.nodes_ordered:
        if node.kind != "inv":
            continue
        kinds.add(INV_KIND_TO_SV[node.inv_kind])
    return sorted(kinds)


def collect_source_sv_classes(tree: Tree) -> List[str]:
    kinds: set[str] = set()
    for node in tree.nodes_ordered:
        if node.kind != "source":
            continue
        kinds.add(SOURCE_KIND_TO_SV[node.source_kind])
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


def node_path_connectable(tree: Tree, node: object) -> bool:
    """clk 节点 RTL path 非空时为真。"""
    if getattr(node, "kind", "") not in ("clk", "cell"):
        return False
    path = getattr(node, "path", "")
    return bool(path)


def any_node_path(tree: Tree) -> bool:
    """任一 clk 节点有可连接 RTL path 时为真，用于决定是否展开测量 interface。"""
    for node in tree.nodes_ordered:
        if node_path_connectable(tree, node):
            return True
    return False


def tree_has_path_and_reg(tree: Tree) -> bool:
    """树内分别存在带 clk path 的节点与带 reg 或 regs 的节点时为真，用于 enable_node_fix。"""
    return any_node_path(tree) and any_reg_configured(tree)


def _append_binding(
    out: List[RegBindingRow],
    sv_access: str,
    member: str,
    raw_path: str,
) -> None:
    spec = parse_reg_path(
        raw_path,
        ctx=f"tree access {sv_access!r} member {member!r}",
    )
    out.append((sv_access, member, spec.path, spec.offset, spec.width))


def _pll_reg_bindings(
    out: List[RegBindingRow],
    tree: Tree,
    node: object,
) -> None:
    assert node.kind == "pll"
    groups = node_output_groups(node)
    regs: dict[str, str] = node.regs
    validate_pll_regs_exact(
        regs,
        node.pll_kind,
        node_name=node.name,
        output_groups=groups,
    )
    if node.pll_kind == "inno":
        for group_id in groups:
            access = sv_node_access(node.name, group_id, groups)
            for key in sorted(INNO_PLL_SHARED_REG_KEYS):
                _append_binding(
                    out, access, f"f_{key}", regs[key]
                )
            p1_key, p2_key = inno_postdiv_reg_keys(group_id)
            _append_binding(
                out, access, "f_postdiv1", regs[p1_key]
            )
            _append_binding(
                out, access, "f_postdiv2", regs[p2_key]
            )
        return
    access = sv_node_access(node.name, "", groups)
    for key, path in sorted(regs.items()):
        _append_binding(out, access, f"f_{key}", path)


def iter_reg_bindings(tree: Tree) -> List[RegBindingRow]:
    out: List[RegBindingRow] = []
    for node in tree.nodes_ordered:
        if not _node_reg_configured(node):
            continue
        if node.kind in SINGLE_REG_NODE_KINDS:
            validate_optional_reg(node.reg, node_name=node.name, kind=node.kind)
            access = sv_node_access(node.name, "", node_output_groups(node))
            _append_binding(out, access, "f_reg", node.reg)
        elif node.kind == "pll":
            _pll_reg_bindings(out, tree, node)
        elif node.kind == "div":
            validate_regs_exact(
                node.regs,
                div_reg_keys_for_kind(node.div_kind),
                node_name=node.name,
                kind=f"div({node.div_kind})",
            )
            groups = node_output_groups(node)
            access = sv_node_access(
                node.name, primary_output_group(node), groups
            )
            for key, path in sorted(node.regs.items()):
                _append_binding(out, access, f"f_{key}", path)
        else:
            flat = flatten_regs(node.regs)
            access = sv_node_access(node.name, "", node_output_groups(node))
            for key, path in sorted(flat.items()):
                _append_binding(out, access, f"f_{key}", path)
    return out

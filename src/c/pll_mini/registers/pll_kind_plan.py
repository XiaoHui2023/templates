from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from model.nodes import PllNode, Tree
from .plan import (
    PLL_DW_ORDER,
    PLL_SC_DIV_KEYS,
    PLL_SC_PD_KEYS,
    PLL_TCI_CTRL_KEYS,
    PLL_TCI_DIV_KEYS,
    _pll_lock_view,
)
from load.regmodel import FieldRef, RegModelIndex
from reg_paths import reg_key_to_c_ident
from .resolve import TreeResolve

PllGroupKey = str


@dataclass(frozen=True)
class PllWritePartTemplate:
    lsb: int
    width: int
    value_expr: str
    comment: str


def _c_compact_hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:X}"


def _field_mask(width: int) -> int:
    if width >= 32:
        return 0xFFFFFFFF
    return (1 << width) - 1


def _is_int_literal(expr: str) -> bool:
    text = expr.strip()
    if not text:
        return False
    if text[0] == "-":
        return text[1:].isdigit()
    return text.isdigit()


@dataclass(frozen=True)
class PllWriteTemplate:
    addr_param: str
    parts: tuple[PllWritePartTemplate, ...]
    reg_path: str
    slot_id: str

    @property
    def value_var(self) -> str:
        if self.addr_param.endswith("_addr"):
            return f"{self.addr_param[:-len('_addr')]}_value"
        return f"{self.addr_param}_value"

    @classmethod
    def _combined_clear_mask_hex(cls, parts: tuple[PllWritePartTemplate, ...]) -> str:
        total = 0
        for part in parts:
            total |= _field_mask(part.width) << part.lsb
        return _c_compact_hex32(total)

    @classmethod
    def _part_set_term(cls, part: PllWritePartTemplate) -> str:
        if _is_int_literal(part.value_expr):
            val = int(part.value_expr)
            return f"({val} << {part.lsb})"
        if part.lsb == 0:
            return part.value_expr
        return f"({part.value_expr} << {part.lsb})"

    @property
    def c_value_update_stmt(self) -> str:
        """同寄存器多 field 合并为一条读改写赋值；set 侧按 field 换行，见 pll_mini_notes。"""
        var = self.value_var
        clear_mask = self._combined_clear_mask_hex(self.parts)
        set_parts = [
            (self._part_set_term(part), part.comment)
            for part in self.parts
        ]
        if not set_parts:
            comments = ", ".join(part.comment for part in self.parts if part.comment)
            suffix = f" // {comments}" if comments else ""
            return f"{var} = {var} & ~{clear_mask};{suffix}"
        cont_indent = " " * (4 + len(var) + 3)
        lines = [f"{var} = ({var} & ~{clear_mask})"]
        for idx, (term, comment) in enumerate(set_parts):
            is_last = idx + 1 == len(set_parts)
            sep = ";" if is_last else ""
            suffix = f" // {comment}" if comment else ""
            lines.append(f"{cont_indent}| {term}{sep}{suffix}")
        return "\n".join(lines)


@dataclass(frozen=True)
class PllFreqBranch:
    freq_hz: int
    assignments: tuple[tuple[str, int], ...]

    @property
    def freq_case_lit(self) -> str:
        return str(self.freq_hz)


@dataclass(frozen=True)
class PllKindPlan:
    pll_kind: str
    fn_name: str
    addr_params: tuple[str, ...]
    cfg_var_names: tuple[str, ...]
    freq_branches: tuple[PllFreqBranch, ...]
    write_templates: tuple[PllWriteTemplate, ...]
    lock_mask_hex: str
    slot_ids: tuple[str, ...]

    @property
    def c_fn_params(self) -> str:
        addr = ", ".join(f"unsigned long {name}" for name in self.addr_params)
        return f"{addr}, unsigned int out_freq_hz"

    @property
    def addr_value_vars(self) -> tuple[str, ...]:
        return tuple(
            f"{name[:-len('_addr')]}_value"
            if name.endswith("_addr")
            else f"{name}_value"
            for name in self.addr_params
        )


@dataclass(frozen=True)
class PllInstancePlan:
    node_name: str
    fn_name: str
    addr_args: tuple[str, ...]
    freq_hz: int
    wait_lock: bool
    lock_addr_macro: str
    lock_mask_hex: str

    @property
    def c_call_args(self) -> str:
        return ", ".join([*self.addr_args, str(self.freq_hz)])


@dataclass(frozen=True)
class PllPlanBundle:
    kind_plans: tuple[PllKindPlan, ...]
    instances: tuple[PllInstancePlan, ...]


PllSlotSpec = tuple[str, tuple[str, ...]]


def _field_ref_signature(ref: FieldRef) -> tuple[int, int]:
    return ref.effective_lsb, ref.effective_width


def _pll_field_specs(
    node: PllNode,
    index: RegModelIndex,
) -> tuple[tuple[str, int, int], ...]:
    items: list[tuple[str, int, int]] = []
    for key in sorted(node.regs.keys()):
        ref = index.resolve(
            node.regs[key],
            ctx=f"pll node {node.name!r} regs[{key!r}]",
        )
        lsb, width = _field_ref_signature(ref)
        items.append((key, lsb, width))
    return tuple(items)


def _pll_reg_grouping(
    node: PllNode,
    index: RegModelIndex,
) -> frozenset[frozenset[str]]:
    reg_to_keys: dict[str, set[str]] = {}
    for key in sorted(node.regs.keys()):
        ref = index.resolve(
            node.regs[key],
            ctx=f"pll node {node.name!r} regs[{key!r}]",
        )
        reg_to_keys.setdefault(ref.reg.path, set()).add(key)
    return frozenset(frozenset(keys) for keys in reg_to_keys.values())


def _validate_pll_group_layout(
    group_key: PllGroupKey,
    nodes: Sequence[PllNode],
    index: RegModelIndex,
) -> None:
    kind = group_key
    label = f"pll_kind {kind!r}"
    ref_node = nodes[0]
    ref_fields = _pll_field_specs(ref_node, index)
    ref_grouping = _pll_reg_grouping(ref_node, index)
    names = ", ".join(n.name for n in nodes)

    field_mismatch = False
    grouping_mismatch = False
    for node in nodes[1:]:
        if _pll_field_specs(node, index) != ref_fields:
            field_mismatch = True
        if _pll_reg_grouping(node, index) != ref_grouping:
            grouping_mismatch = True

    if field_mismatch:
        raise ValueError(
            f"{label} 的活动节点 {names} 各逻辑键 field 的 lsb、位宽不一致，"
            f"同型号须使用相同寄存器规格"
        )
    if grouping_mismatch:
        raise ValueError(
            f"{label} 的活动节点 {names} 逻辑键到物理寄存器的合并分组不一致，"
            f"同型号须使用相同寄存器规格"
        )


def _validate_pll_freq_cfg(
    group_key: PllGroupKey,
    nodes: Sequence[PllNode],
    resolved: TreeResolve,
) -> dict[int, dict[str, int]]:
    kind = group_key
    label = f"pll_kind {kind!r}"
    by_freq: dict[int, dict[str, int]] = {}
    for node in nodes:
        state = resolved.by_name[node.name]
        out_hz = state.resolved_freq
        cfg = dict(state.pll_cfg)
        prev = by_freq.get(out_hz)
        if prev is not None and prev != cfg:
            raise ValueError(
                f"{label} 输出频率 {out_hz} Hz 在节点 {node.name!r} "
                f"与先前节点推算的分频不一致"
            )
        by_freq[out_hz] = cfg
    return by_freq


def _pll_kind_fn_name(pll_kind: str) -> str:
    return f"pll_mini_config_pll_{pll_kind}"


def _slot_param_name(slot_id: str) -> str:
    return f"{slot_id}_addr"


def _keys_slot_specs(
    keys: Sequence[str],
    slot_prefix: str,
    node: PllNode,
    index: RegModelIndex,
) -> tuple[PllSlotSpec, ...]:
    """按节点上逻辑键共址关系拆成命名槽；与路径字符串无关。"""
    reg_paths_order: list[str] = []
    keys_by_reg: dict[str, list[str]] = {}
    for key in keys:
        ref = index.resolve(
            node.regs[key],
            ctx=f"pll node {node.name!r} regs[{key!r}]",
        )
        reg_path = ref.reg.path
        if reg_path not in keys_by_reg:
            reg_paths_order.append(reg_path)
            keys_by_reg[reg_path] = []
        keys_by_reg[reg_path].append(key)
    if len(reg_paths_order) == 1:
        return ((slot_prefix, tuple(keys)),)
    return tuple(
        (f"{slot_prefix}_{idx}", tuple(keys_by_reg[reg_path]))
        for idx, reg_path in enumerate(reg_paths_order)
    )


def _kind_write_slot_specs(
    pll_kind: str,
    node: PllNode,
    index: RegModelIndex,
    output_groups: list[str],
) -> tuple[PllSlotSpec, ...]:
    if pll_kind == "sc":
        return (
            *_keys_slot_specs(PLL_SC_PD_KEYS, "sc_pd", node, index),
            *_keys_slot_specs(PLL_SC_DIV_KEYS, "sc_div", node, index),
        )
    if pll_kind == "tci":
        return (
            *_keys_slot_specs(PLL_TCI_CTRL_KEYS, "tci_ctrl", node, index),
            *_keys_slot_specs(PLL_TCI_DIV_KEYS, "tci_div", node, index),
        )
    if pll_kind == "dw":
        reg_paths_order: list[str] = []
        keys_by_reg: dict[str, list[str]] = {}
        for key in PLL_DW_ORDER:
            ref = index.resolve(
                node.regs[key],
                ctx=f"pll node {node.name!r} regs[{key!r}]",
            )
            reg_path = ref.reg.path
            if reg_path not in keys_by_reg:
                reg_paths_order.append(reg_path)
                keys_by_reg[reg_path] = []
            keys_by_reg[reg_path].append(key)
        return tuple(
            (f"dw_{idx}", tuple(keys_by_reg[reg_path]))
            for idx, reg_path in enumerate(reg_paths_order)
        )
    if pll_kind == "inno":
        from reg_paths import inno_postdiv_reg_keys

        specs: list[PllSlotSpec] = [
            ("inno_pd", ("pd",)),
            *_keys_slot_specs(("refdiv", "fbdiv"), "inno_div", node, index),
        ]
        for group_id in output_groups:
            p1_key, p2_key = inno_postdiv_reg_keys(group_id)
            specs.extend(
                _keys_slot_specs(
                    (p1_key, p2_key),
                    f"inno_postdiv_{group_id}",
                    node,
                    index,
                )
            )
        return tuple(specs)
    raise ValueError(f"unknown pll_kind {pll_kind!r}")


def _unique_slot_specs_in_order(
    slot_specs: tuple[PllSlotSpec, ...],
) -> tuple[PllSlotSpec, ...]:
    seen: set[str] = set()
    ordered: list[PllSlotSpec] = []
    for spec in slot_specs:
        slot_id = spec[0]
        if slot_id in seen:
            continue
        seen.add(slot_id)
        ordered.append(spec)
    return tuple(ordered)


def _slot_id_for_reg_key(
    key: str,
    slot_specs: tuple[PllSlotSpec, ...],
) -> str:
    for slot_id, keys in slot_specs:
        if key in keys:
            return slot_id
    raise ValueError(f"pll 逻辑键 {key!r} 不在 slot_specs 中")


def _group_reg_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
    keys: Sequence[str],
    *,
    slot_id: str,
    value_expr_for_key,
    comment_for_key,
) -> tuple[PllWriteTemplate, ...]:
    """按 YAML 逻辑键顺序分组，同物理寄存器多 field 合并为一次写。"""
    groups: list[tuple[str, list[PllWritePartTemplate]]] = []
    for key in keys:
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"pll node {template_node.name!r} regs[{key!r}]",
        )
        reg_path = ref.reg.path
        part = PllWritePartTemplate(
            lsb=ref.effective_lsb,
            width=ref.effective_width,
            value_expr=value_expr_for_key(key),
            comment=comment_for_key(key),
        )
        if groups and groups[-1][0] == reg_path:
            groups[-1][1].append(part)
        else:
            groups.append((reg_path, [part]))
    if len(groups) == 1:
        reg_path, parts = groups[0]
        return (
            PllWriteTemplate(
                _slot_param_name(slot_id),
                tuple(parts),
                reg_path,
                slot_id,
            ),
        )
    return tuple(
        PllWriteTemplate(
            _slot_param_name(f"{slot_id}_{idx}"),
            tuple(parts),
            reg_path,
            f"{slot_id}_{idx}",
        )
        for idx, (reg_path, parts) in enumerate(groups)
    )


def _sc_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    pd_down = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        slot_id="sc_pd",
        value_expr_for_key=lambda _key: "1",
        comment_for_key=lambda key: "power-down" if key == "vocpd" else key,
    )
    div_cfg = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_DIV_KEYS,
        slot_id="sc_div",
        value_expr_for_key=reg_key_to_c_ident,
        comment_for_key=lambda key: key,
    )
    pd_en = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        slot_id="sc_pd",
        value_expr_for_key=lambda _key: "0",
        comment_for_key=lambda key: "enable" if key == "vocpd" else key,
    )
    return pd_down + div_cfg + pd_en


def _tci_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    slot_specs = _unique_slot_specs_in_order(
        _kind_write_slot_specs("tci", template_node, index, [])
    )
    templates: list[PllWriteTemplate] = []

    def _append_field_write(key: str, value_expr: str, comment: str) -> None:
        sid = _slot_id_for_reg_key(key, slot_specs)
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"pll node {template_node.name!r} regs[{key!r}]",
        )
        templates.append(
            PllWriteTemplate(
                _slot_param_name(sid),
                (
                    PllWritePartTemplate(
                        ref.effective_lsb,
                        ref.effective_width,
                        value_expr,
                        comment,
                    ),
                ),
                ref.reg.path,
                sid,
            )
        )

    for key, val in zip(PLL_TCI_CTRL_KEYS, (1, 0, 1), strict=True):
        comment = "bypass=1 pwrdn=0 reset=1" if key == "bypass" else key
        _append_field_write(key, str(val), comment)
    for key in PLL_TCI_DIV_KEYS:
        _append_field_write(key, reg_key_to_c_ident(key), key)
    _append_field_write("reset", "0", "reset release")
    _append_field_write("bypass", "0", "bypass off")
    return tuple(templates)


def _dw_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    slot_specs = _kind_write_slot_specs("dw", template_node, index, [])
    templates: list[PllWriteTemplate] = []
    for slot_id, keys in slot_specs:
        parts: list[PllWritePartTemplate] = []
        reg_path = ""
        for key in keys:
            ref = index.resolve(
                template_node.regs[key],
                ctx=f"pll node {template_node.name!r} regs[{key!r}]",
            )
            reg_path = ref.reg.path
            parts.append(
                PllWritePartTemplate(
                    ref.effective_lsb,
                    ref.effective_width,
                    reg_key_to_c_ident(key),
                    key,
                )
            )
        templates.append(
            PllWriteTemplate(
                _slot_param_name(slot_id),
                tuple(parts),
                reg_path,
                slot_id,
            )
        )
    return tuple(templates)


def _inno_write_templates(
    output_groups: list[str],
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    from reg_paths import inno_postdiv_reg_keys

    templates: list[PllWriteTemplate] = []
    pd_ref = index.resolve(
        template_node.regs["pd"],
        ctx=f"pll node {template_node.name!r} regs.pd",
    )
    templates.append(
        PllWriteTemplate(
            _slot_param_name("inno_pd"),
            (
                PllWritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "1",
                    "pd assert",
                ),
            ),
            pd_ref.reg.path,
            "inno_pd",
        )
    )
    templates.extend(
        _group_reg_write_templates(
            index,
            template_node,
            ("refdiv", "fbdiv"),
            slot_id="inno_div",
            value_expr_for_key=reg_key_to_c_ident,
            comment_for_key=lambda key: key,
        )
    )
    templates.append(
        PllWriteTemplate(
            _slot_param_name("inno_pd"),
            (
                PllWritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "0",
                    "pd release",
                ),
            ),
            pd_ref.reg.path,
            "inno_pd",
        )
    )
    if not output_groups:
        raise ValueError(
            f"pll_kind inno 须有两路输出，output_groups 为空"
        )
    for group_id in output_groups:
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        templates.extend(
            _group_reg_write_templates(
                index,
                template_node,
                (p1_key, p2_key),
                slot_id=f"inno_postdiv_{group_id}",
                value_expr_for_key=reg_key_to_c_ident,
                comment_for_key=lambda key, p1=p1_key, gid=group_id: (
                    f"out[{gid}] {key}" if key == p1 else key
                ),
            )
        )
    return tuple(templates)


def _cfg_var_names_for_kind(
    pll_kind: str,
    output_groups: list[str],
    cfg_by_freq: dict[int, dict[str, int]],
) -> tuple[str, ...]:
    keys: set[str] = set()
    for cfg in cfg_by_freq.values():
        keys.update(cfg.keys())
    if pll_kind == "sc":
        return tuple(k for k in PLL_SC_DIV_KEYS if k in keys)
    if pll_kind == "tci":
        return tuple(k for k in PLL_TCI_DIV_KEYS if k in keys)
    if pll_kind == "dw":
        return tuple(k for k in PLL_DW_ORDER if k in keys)
    if pll_kind == "inno":
        ordered: list[str] = ["refdiv", "fbdiv"]
        from reg_paths import inno_postdiv_reg_keys

        for group_id in output_groups:
            ordered.extend(inno_postdiv_reg_keys(group_id))
        return tuple(k for k in ordered if k in keys)
    raise ValueError(f"unknown pll_kind {pll_kind!r}")


def _kind_write_templates(
    pll_kind: str,
    output_groups: list[str],
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    if pll_kind == "sc":
        return _sc_write_templates(index, template_node)
    if pll_kind == "tci":
        return _tci_write_templates(index, template_node)
    if pll_kind == "dw":
        return _dw_write_templates(index, template_node)
    if pll_kind == "inno":
        return _inno_write_templates(output_groups, index, template_node)
    raise ValueError(f"unknown pll_kind {pll_kind!r}")


def _slot_macro_maps(
    nodes: Sequence[PllNode],
    index: RegModelIndex,
    slot_specs: tuple[PllSlotSpec, ...],
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    slot_order = tuple(slot_id for slot_id, _ in slot_specs)
    maps: list[dict[str, str]] = []
    for node in nodes:
        macros: dict[str, str] = {}
        for slot_id, keys in slot_specs:
            ref = index.resolve(
                node.regs[keys[0]],
                ctx=f"pll node {node.name!r} regs[{keys[0]!r}]",
            )
            macros[slot_id] = ref.reg.addr_macro
        maps.append(macros)
    return maps, slot_order


def _slot_to_rep_min_params(
    macro_maps: Sequence[dict[str, str]],
    slot_order: Sequence[str],
) -> dict[str, str]:
    """两槽仅在每个实例上地址宏都相同时合并，使形参个数最少。"""
    parent: dict[str, str] = {sid: sid for sid in slot_order}

    def find(sid: str) -> str:
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid

    def unite(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if slot_order.index(ra) > slot_order.index(rb):
            ra, rb = rb, ra
        parent[rb] = ra

    for i, slot_a in enumerate(slot_order):
        for slot_b in slot_order[i + 1 :]:
            if all(mm[slot_a] == mm[slot_b] for mm in macro_maps):
                unite(slot_a, slot_b)

    return {sid: find(sid) for sid in slot_order}


def _consolidate_pll_addr_params(
    pll_kind: str,
    write_templates: tuple[PllWriteTemplate, ...],
    nodes: Sequence[PllNode],
    index: RegModelIndex,
    slot_specs: tuple[PllSlotSpec, ...],
) -> tuple[tuple[PllWriteTemplate, ...], tuple[str, ...], tuple[str, ...]]:
    """同型号全部实例上地址宏一致的槽合并；调用处按代表槽取各实例自己的宏。"""
    macro_maps, slot_order = _slot_macro_maps(nodes, index, slot_specs)
    slot_to_rep = _slot_to_rep_min_params(macro_maps, slot_order)

    rep_order: list[str] = []
    for wt in write_templates:
        rep = slot_to_rep[wt.slot_id]
        if rep not in rep_order:
            rep_order.append(rep)

    n_unique = len(rep_order)
    rep_to_param: dict[str, str] = {}
    for rep in rep_order:
        if n_unique == 1:
            rep_to_param[rep] = f"{pll_kind}_addr"
        else:
            rep_to_param[rep] = _slot_param_name(rep)

    remapped: list[PllWriteTemplate] = []
    for wt in write_templates:
        rep = slot_to_rep[wt.slot_id]
        remapped.append(
            PllWriteTemplate(
                rep_to_param[rep],
                wt.parts,
                wt.reg_path,
                wt.slot_id,
            )
        )

    addr_params: list[str] = []
    param_to_slot: dict[str, str] = {}
    for wt in remapped:
        if wt.addr_param in param_to_slot:
            continue
        param_to_slot[wt.addr_param] = slot_to_rep[wt.slot_id]
        addr_params.append(wt.addr_param)

    addr_param_slot_ids = tuple(param_to_slot[p] for p in addr_params)

    return tuple(remapped), tuple(addr_params), addr_param_slot_ids


def _freq_branches(
    cfg_by_freq: dict[int, dict[str, int]],
    cfg_logical_keys: tuple[str, ...],
) -> tuple[PllFreqBranch, ...]:
    branches: list[PllFreqBranch] = []
    for freq_hz in sorted(cfg_by_freq):
        cfg = cfg_by_freq[freq_hz]
        assignments = tuple(
            (reg_key_to_c_ident(name), cfg[name]) for name in cfg_logical_keys
        )
        branches.append(PllFreqBranch(freq_hz=freq_hz, assignments=assignments))
    return tuple(branches)


def _instance_addr_args_by_slots(
    node: PllNode,
    index: RegModelIndex,
    addr_param_slot_ids: Sequence[str],
    slot_specs: tuple[PllSlotSpec, ...],
) -> tuple[str, ...]:
    slot_to_keys = {slot_id: keys for slot_id, keys in slot_specs}
    args: list[str] = []
    for slot_id in addr_param_slot_ids:
        keys = slot_to_keys.get(slot_id)
        if keys is None:
            raise ValueError(
                f"pll 节点 {node.name!r} 写槽 {slot_id!r} 与型号模板不一致"
            )
        ref = index.resolve(
            node.regs[keys[0]],
            ctx=f"pll node {node.name!r} regs[{keys[0]!r}]",
        )
        args.append(ref.reg.addr_macro)
    return tuple(args)


def _collect_configured_pll_nodes(
    tree: Tree,
    resolved: TreeResolve,
) -> list[PllNode]:
    nodes: list[PllNode] = []
    for node in tree.nodes_ordered:
        if not isinstance(node, PllNode) or not node.regs:
            continue
        if resolved.by_name[node.name].pll_cfg:
            nodes.append(node)
    return nodes


def build_pll_plan(
    tree: Tree,
    index: RegModelIndex,
    resolved: TreeResolve,
) -> PllPlanBundle:
    active = _collect_configured_pll_nodes(tree, resolved)
    groups: dict[PllGroupKey, list[PllNode]] = {}
    for node in active:
        key = node.pll_kind
        groups.setdefault(key, []).append(node)

    kind_plans: list[PllKindPlan] = []
    instances: list[PllInstancePlan] = []

    for group_key in sorted(groups.keys()):
        nodes = groups[group_key]
        pll_kind = group_key
        _validate_pll_group_layout(group_key, nodes, index)
        cfg_by_freq = _validate_pll_freq_cfg(group_key, nodes, resolved)
        template_node = nodes[0]
        output_groups = template_node.output_groups
        slot_specs = _unique_slot_specs_in_order(
            _kind_write_slot_specs(pll_kind, template_node, index, output_groups)
        )
        write_templates_raw = _kind_write_templates(
            pll_kind, output_groups, index, template_node
        )
        write_templates, addr_params, addr_param_slot_ids = (
            _consolidate_pll_addr_params(
                pll_kind, write_templates_raw, nodes, index, slot_specs
            )
        )
        cfg_logical_keys = _cfg_var_names_for_kind(
            pll_kind, output_groups, cfg_by_freq
        )
        cfg_var_names = tuple(
            reg_key_to_c_ident(name) for name in cfg_logical_keys
        )
        slot_ids = tuple(spec[0] for spec in slot_specs)
        _, lock_mask_hex = _pll_lock_view(index, template_node)
        fn_name = _pll_kind_fn_name(pll_kind)
        kind_plans.append(
            PllKindPlan(
                pll_kind=pll_kind,
                fn_name=fn_name,
                addr_params=addr_params,
                cfg_var_names=cfg_var_names,
                freq_branches=_freq_branches(cfg_by_freq, cfg_logical_keys),
                write_templates=write_templates,
                lock_mask_hex=lock_mask_hex,
                slot_ids=slot_ids,
            )
        )
        for node in nodes:
            lock_addr_macro, _ = _pll_lock_view(index, node)
            node_slot_specs = _unique_slot_specs_in_order(
                _kind_write_slot_specs(pll_kind, node, index, output_groups)
            )
            if node_slot_specs != slot_specs:
                raise ValueError(
                    f"pll_kind {pll_kind!r} 节点 {node.name!r} 写槽与模板不一致"
                )
            instances.append(
                PllInstancePlan(
                    node_name=node.name,
                    fn_name=fn_name,
                    addr_args=_instance_addr_args_by_slots(
                        node, index, addr_param_slot_ids, slot_specs
                    ),
                    freq_hz=resolved.by_name[node.name].resolved_freq,
                    wait_lock=True,
                    lock_addr_macro=lock_addr_macro,
                    lock_mask_hex=lock_mask_hex,
                )
            )

    return PllPlanBundle(
        kind_plans=tuple(kind_plans),
        instances=tuple(instances),
    )

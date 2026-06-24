from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from nodes import PllNode, Tree
from plan import (
    PLL_DW_ORDER,
    PLL_SC_DIV_KEYS,
    PLL_SC_PD_KEYS,
    PLL_TCI_CTRL_KEYS,
    PLL_TCI_DIV_KEYS,
    _pll_lock_view,
    expand_pll_patches,
    merge_field_patches,
)
from regmodel import FieldRef, RegModelIndex
from resolve import ResolvedNode, TreeResolve

PllGroupKey = Tuple[str, int]


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
    def _part_set_term(cls, part: PllWritePartTemplate) -> str | None:
        if _is_int_literal(part.value_expr):
            val = int(part.value_expr)
            if val == 0:
                return None
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
            (term, part.comment)
            for part in self.parts
            if (term := self._part_set_term(part)) is not None
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
    output_count: int
    fn_name: str
    addr_params: tuple[str, ...]
    cfg_var_names: tuple[str, ...]
    freq_branches: tuple[PllFreqBranch, ...]
    write_templates: tuple[PllWriteTemplate, ...]
    lock_mask_hex: str
    slot_tails: tuple[str, ...]

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


def reg_path_suffix(path: str) -> str:
    parts = path.split(".")
    if len(parts) < 2:
        return path
    return ".".join(parts[1:])


def _field_ref_signature(ref: FieldRef) -> tuple[int, int]:
    return ref.effective_lsb, ref.effective_width


def _pll_layout_signature(
    node: PllNode,
    index: RegModelIndex,
) -> tuple[tuple[str, str, tuple[int, int]], ...]:
    items: list[tuple[str, str, tuple[int, int]]] = []
    for key in sorted(node.regs.keys()):
        ref = index.resolve(
            node.regs[key],
            ctx=f"pll node {node.name!r} regs[{key!r}]",
        )
        items.append((key, reg_path_suffix(node.regs[key]), _field_ref_signature(ref)))
    return tuple(items)


def _validate_pll_group_layout(
    group_key: PllGroupKey,
    nodes: Sequence[PllNode],
    index: RegModelIndex,
) -> None:
    kind, output_count = group_key
    label = f"pll_kind {kind!r} output_count {output_count}"
    suffix_maps = [
        {key: reg_path_suffix(node.regs[key]) for key in sorted(node.regs)}
        for node in nodes
    ]
    unique_suffix = {tuple(sorted(m.items())) for m in suffix_maps}
    if len(unique_suffix) != 1:
        names = ", ".join(n.name for n in nodes)
        raise ValueError(
            f"{label} 的活动节点 {names} 寄存器路径后缀不一致，"
            f"同型号须使用相同寄存器规格"
        )
    signatures = [_pll_layout_signature(node, index) for node in nodes]
    if len(set(signatures)) != 1:
        names = ", ".join(n.name for n in nodes)
        raise ValueError(
            f"{label} 的活动节点 {names} field 位域布局不一致，"
            f"同型号须使用相同寄存器规格"
        )


def _validate_pll_freq_cfg(
    group_key: PllGroupKey,
    nodes: Sequence[PllNode],
    resolved: TreeResolve,
) -> dict[int, dict[str, int]]:
    kind, output_count = group_key
    label = f"pll_kind {kind!r} output_count {output_count}"
    by_freq: dict[int, dict[str, int]] = {}
    for node in nodes:
        state = resolved.by_name[node.name]
        cfg = dict(state.pll_cfg)
        prev = by_freq.get(node.freq)
        if prev is not None and prev != cfg:
            raise ValueError(
                f"{label} 输出频率 {node.freq} Hz 在节点 {node.name!r} "
                f"与先前节点推算的分频不一致"
            )
        by_freq[node.freq] = cfg
    return by_freq


def _pll_kind_fn_name(pll_kind: str) -> str:
    return f"pll_mini_config_pll_{pll_kind}"


def _slot_param_name(reg_tail: str) -> str:
    return f"{reg_tail}_addr"


def _group_reg_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
    keys: Sequence[str],
    *,
    value_expr_for_key,
    comment_for_key,
) -> tuple[PllWriteTemplate, ...]:
    """按 YAML 路径解析出的寄存器名分组，同寄存器多 field 合并为一次写。"""
    groups: list[tuple[str, list[PllWritePartTemplate]]] = []
    for key in keys:
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"pll node {template_node.name!r} regs[{key!r}]",
        )
        tail = ref.reg.path.split(".")[-1]
        part = PllWritePartTemplate(
            lsb=ref.effective_lsb,
            width=ref.effective_width,
            value_expr=value_expr_for_key(key),
            comment=comment_for_key(key),
        )
        if groups and groups[-1][0] == tail:
            groups[-1][1].append(part)
        else:
            groups.append((tail, [part]))
    return tuple(
        PllWriteTemplate(_slot_param_name(tail), tuple(parts))
        for tail, parts in groups
    )


def _sc_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    pd_down = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        value_expr_for_key=lambda _key: "1",
        comment_for_key=lambda key: "power-down" if key == "vocpd" else key,
    )
    div_cfg = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_DIV_KEYS,
        value_expr_for_key=lambda key: key,
        comment_for_key=lambda key: key,
    )
    pd_en = _group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        value_expr_for_key=lambda _key: "0",
        comment_for_key=lambda key: "enable" if key == "vocpd" else key,
    )
    return pd_down + div_cfg + pd_en


def _tci_write_templates() -> tuple[PllWriteTemplate, ...]:
    ctrl_tail = "ctrl"
    div_tail = "div"
    ctrl_lsb = {"bypass": 0, "pwrdn": 1, "reset": 2}
    div_lsb = {"clkod": 0, "clkf": 8, "clkr": 16, "bwadj": 24}
    ctrl_init = tuple(
        PllWritePartTemplate(
            lsb=ctrl_lsb[key],
            width=1,
            value_expr=str(val),
            comment="bypass=1 pwrdn=0 reset=1" if key == "bypass" else key,
        )
        for key, val in zip(PLL_TCI_CTRL_KEYS, (1, 0, 1), strict=True)
    )
    div_parts = tuple(
        PllWritePartTemplate(
            lsb=div_lsb[key],
            width=8,
            value_expr=key,
            comment=key,
        )
        for key in PLL_TCI_DIV_KEYS
    )
    return (
        PllWriteTemplate(_slot_param_name(ctrl_tail), ctrl_init),
        PllWriteTemplate(_slot_param_name(div_tail), div_parts),
        PllWriteTemplate(
            _slot_param_name(ctrl_tail),
            (PllWritePartTemplate(2, 1, "0", "reset release"),),
        ),
        PllWriteTemplate(
            _slot_param_name(ctrl_tail),
            (PllWritePartTemplate(0, 1, "0", "bypass off"),),
        ),
    )


def _dw_write_templates(
    index: RegModelIndex,
    template_node: PllNode,
) -> tuple[PllWriteTemplate, ...]:
    by_reg: dict[str, list[PllWritePartTemplate]] = {}
    for key in PLL_DW_ORDER:
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"pll node {template_node.name!r} regs[{key!r}]",
        )
        tail = ref.reg.path.split(".")[-1]
        by_reg.setdefault(tail, []).append(
            PllWritePartTemplate(ref.effective_lsb, ref.effective_width, key, key)
        )
    return tuple(
        PllWriteTemplate(_slot_param_name(tail), tuple(parts))
        for tail, parts in by_reg.items()
    )


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
    pd_tail = pd_ref.reg.path.split(".")[-1]
    templates.append(
        PllWriteTemplate(
            _slot_param_name(pd_tail),
            (
                PllWritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "1",
                    "pd assert",
                ),
            ),
        )
    )
    templates.extend(
        _group_reg_write_templates(
            index,
            template_node,
            ("refdiv", "fbdiv"),
            value_expr_for_key=lambda key: key,
            comment_for_key=lambda key: key,
        )
    )
    templates.append(
        PllWriteTemplate(
            _slot_param_name(pd_tail),
            (
                PllWritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "0",
                    "pd release",
                ),
            ),
        )
    )
    if not output_groups:
        templates.extend(
            _group_reg_write_templates(
                index,
                template_node,
                ("postdiv1", "postdiv2"),
                value_expr_for_key=lambda key: key,
                comment_for_key=lambda key: key,
            )
        )
        return tuple(templates)
    for group_id in output_groups:
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        templates.extend(
            _group_reg_write_templates(
                index,
                template_node,
                (p1_key, p2_key),
                value_expr_for_key=lambda key: key,
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
        if not output_groups:
            ordered.extend(["postdiv1", "postdiv2"])
        else:
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
        return _tci_write_templates()
    if pll_kind == "dw":
        return _dw_write_templates(index, template_node)
    if pll_kind == "inno":
        return _inno_write_templates(output_groups, index, template_node)
    raise ValueError(f"unknown pll_kind {pll_kind!r}")


def _slot_tails_from_writes(writes: tuple[PllWriteTemplate, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    tails: list[str] = []
    for wt in writes:
        tail = wt.addr_param[: -len("_addr")]
        if tail in seen:
            continue
        seen.add(tail)
        tails.append(tail)
    return tuple(tails)


def _addr_params_from_writes(writes: tuple[PllWriteTemplate, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    params: list[str] = []
    for wt in writes:
        if wt.addr_param in seen:
            continue
        seen.add(wt.addr_param)
        params.append(wt.addr_param)
    return tuple(params)


def _freq_branches(
    cfg_by_freq: dict[int, dict[str, int]],
    cfg_var_names: tuple[str, ...],
) -> tuple[PllFreqBranch, ...]:
    branches: list[PllFreqBranch] = []
    for freq_hz in sorted(cfg_by_freq):
        cfg = cfg_by_freq[freq_hz]
        assignments = tuple((name, cfg[name]) for name in cfg_var_names)
        branches.append(PllFreqBranch(freq_hz=freq_hz, assignments=assignments))
    return tuple(branches)


def _instance_addr_args(
    node: PllNode,
    index: RegModelIndex,
    state: ResolvedNode,
    slot_tails: tuple[str, ...],
) -> tuple[str, ...]:
    writes = merge_field_patches(expand_pll_patches(index, node, state))
    by_tail: dict[str, str] = {}
    for step in writes:
        tail = step.reg.path.split(".")[-1]
        by_tail[tail] = step.addr_macro
    missing = [tail for tail in slot_tails if tail not in by_tail]
    if missing:
        raise ValueError(
            f"pll 节点 {node.name!r} 缺少寄存器 {missing!r} 的地址"
        )
    return tuple(by_tail[tail] for tail in slot_tails)


def _collect_active_pll_nodes(
    tree: Tree,
    resolved: TreeResolve,
) -> list[PllNode]:
    nodes: list[PllNode] = []
    for node in tree.nodes_ordered:
        if not isinstance(node, PllNode) or not node.regs:
            continue
        if resolved.by_name[node.name].active:
            nodes.append(node)
    return nodes


def build_pll_plan(
    tree: Tree,
    index: RegModelIndex,
    resolved: TreeResolve,
) -> PllPlanBundle:
    active = _collect_active_pll_nodes(tree, resolved)
    groups: dict[PllGroupKey, list[PllNode]] = {}
    for node in active:
        key = (node.pll_kind, node.output_count)
        groups.setdefault(key, []).append(node)

    kind_plans: list[PllKindPlan] = []
    instances: list[PllInstancePlan] = []

    for group_key in sorted(groups.keys()):
        nodes = groups[group_key]
        pll_kind, output_count = group_key
        _validate_pll_group_layout(group_key, nodes, index)
        cfg_by_freq = _validate_pll_freq_cfg(group_key, nodes, resolved)
        template_node = nodes[0]
        output_groups = template_node.output_groups
        write_templates = _kind_write_templates(
            pll_kind, output_groups, index, template_node
        )
        cfg_var_names = _cfg_var_names_for_kind(
            pll_kind, output_groups, cfg_by_freq
        )
        addr_params = _addr_params_from_writes(write_templates)
        slot_tails = _slot_tails_from_writes(write_templates)
        _, lock_mask_hex = _pll_lock_view(index, template_node)
        fn_name = _pll_kind_fn_name(pll_kind)
        kind_plans.append(
            PllKindPlan(
                pll_kind=pll_kind,
                output_count=output_count,
                fn_name=fn_name,
                addr_params=addr_params,
                cfg_var_names=cfg_var_names,
                freq_branches=_freq_branches(cfg_by_freq, cfg_var_names),
                write_templates=write_templates,
                lock_mask_hex=lock_mask_hex,
                slot_tails=slot_tails,
            )
        )
        for node in nodes:
            state = resolved.by_name[node.name]
            wait_lock = not (pll_kind == "inno" and output_count > 1)
            lock_addr_macro = ""
            if wait_lock:
                lock_addr_macro, _ = _pll_lock_view(index, node)
            instances.append(
                PllInstancePlan(
                    node_name=node.name,
                    fn_name=fn_name,
                    addr_args=_instance_addr_args(
                        node, index, state, slot_tails
                    ),
                    freq_hz=node.freq,
                    wait_lock=wait_lock,
                    lock_addr_macro=lock_addr_macro,
                    lock_mask_hex=lock_mask_hex,
                )
            )

    return PllPlanBundle(
        kind_plans=tuple(kind_plans),
        instances=tuple(instances),
    )

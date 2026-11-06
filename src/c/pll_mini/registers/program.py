from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Sequence

from load.regmodel import RegModelIndex, validate_field_value
from node.base import NodeBase
from node.synthesis import SynthesizedNode
from node.errors import node_context
from reg_paths import reg_key_to_c_ident

if TYPE_CHECKING:
    from registers.resolve import TreeResolve


@dataclass(frozen=True)
class WritePartTemplate:
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
class WriteTemplate:
    addr_param: str
    parts: tuple[WritePartTemplate, ...]
    reg_path: str
    slot_id: str

    @property
    def value_var(self) -> str:
        if self.addr_param.endswith("_addr"):
            return f"{self.addr_param[: -len('_addr')]}_value"
        return f"{self.addr_param}_value"

    @classmethod
    def _combined_clear_mask_hex(cls, parts: tuple[WritePartTemplate, ...]) -> str:
        total = 0
        for part in parts:
            total |= _field_mask(part.width) << part.lsb
        return _c_compact_hex32(total)

    @classmethod
    def _part_set_term(cls, part: WritePartTemplate) -> str:
        if _is_int_literal(part.value_expr):
            val = int(part.value_expr)
            return f"({val} << {part.lsb})"
        if part.lsb == 0:
            return part.value_expr
        return f"({part.value_expr} << {part.lsb})"

    @property
    def c_value_update_stmt(self) -> str:
        """Combine field updates for one stage, preserving the untouched bits."""
        var = self.value_var
        clear_mask = self._combined_clear_mask_hex(self.parts)
        set_parts = [(self._part_set_term(part), part.comment) for part in self.parts]
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
class ValueBranch:
    freq_hz: int
    assignments: tuple[tuple[str, int], ...]

    @property
    def freq_case_lit(self) -> str:
        return str(self.freq_hz)


@dataclass(frozen=True)
class FunctionPlan:
    fn_name: str
    addr_params: tuple[str, ...]
    cfg_var_names: tuple[str, ...]
    freq_branches: tuple[ValueBranch, ...]
    write_templates: tuple[WriteTemplate, ...]

    @property
    def c_fn_params(self) -> str:
        addr = ", ".join(f"unsigned long {name}" for name in self.addr_params)
        return f"{addr}, unsigned int out_freq_hz"

    @property
    def addr_value_vars(self) -> tuple[str, ...]:
        return tuple(
            f"{name[: -len('_addr')]}_value"
            if name.endswith("_addr")
            else f"{name}_value"
            for name in self.addr_params
        )

    @property
    def c_definition(self) -> str:
        lines = [f"static void {self.fn_name}({self.c_fn_params})", "{"]
        lines.extend(
            f"    unsigned int {name};"
            for name in (*self.cfg_var_names, *self.addr_value_vars)
        )
        lines.append("    switch (out_freq_hz) {")
        for branch in self.freq_branches:
            lines.append(f"    case {branch.freq_case_lit}:")
            lines.extend(
                f"        {name} = {value};" for name, value in branch.assignments
            )
            lines.append("        break;")
        lines.extend(("    default:", "        return;", "    }"))
        lines.extend(
            f"    cpu_config_read(&{value}, {addr});"
            for addr, value in zip(self.addr_params, self.addr_value_vars, strict=True)
        )
        for write in self.write_templates:
            lines.extend(
                (
                    "",
                    f"    {write.c_value_update_stmt}",
                    f"    cpu_config_write({write.addr_param}, {write.value_var});",
                )
            )
        return "\n".join((*lines, "}"))


@dataclass(frozen=True)
class InstancePlan:
    node_name: str
    fn_name: str
    addr_args: tuple[str, ...]
    freq_hz: int
    poll_ready: bool
    ready_addr_macro: str
    ready_mask_hex: str
    poll_function: str
    poll_parameter: str

    @property
    def c_call_args(self) -> str:
        return ", ".join([*self.addr_args, str(self.freq_hz)])


@dataclass(frozen=True)
class ProgramBundle:
    function_plans: tuple[FunctionPlan, ...]
    instances: tuple[InstancePlan, ...]

    @cached_property
    def code(self):
        from .plan import CodeSections

        definitions = []
        after = []
        polls = {}
        for inst in self.instances:
            if inst.poll_ready:
                polls.setdefault(inst.poll_function, []).append(inst)
        for name, instances in polls.items():
            masks = {inst.ready_mask_hex for inst in instances}
            mask = next(iter(masks)) if len(masks) == 1 else None
            value = int(mask, 16) if mask else 0
            fixed = mask if value and value & (value - 1) == 0 else None
            mask_parameter = instances[0].poll_parameter
            parameter = "" if fixed else f", unsigned int {mask_parameter}"
            definitions.append(
                "\n".join(
                    (
                        f"static void {name}(unsigned long addr{parameter})",
                        "{",
                        "    unsigned int data;",
                        "",
                        "    cpu_config_read(&data, addr);",
                        f"    while ((data & {fixed or mask_parameter}) == 0)",
                        "        cpu_config_read(&data, addr);",
                        "}",
                    )
                )
            )
            after.extend(
                f"    {name}({inst.ready_addr_macro}"
                + ("" if fixed else f", {inst.ready_mask_hex}")
                + ");"
                for inst in instances
            )
        definitions.extend(fn.c_definition for fn in self.function_plans)
        return CodeSections(
            definitions=tuple(definitions),
            calls=tuple(
                f"    {inst.fn_name}({inst.c_call_args});" for inst in self.instances
            ),
            after_calls=tuple(after),
            register_macros=tuple(
                macro
                for inst in self.instances
                for macro in (*inst.addr_args, inst.ready_addr_macro)
                if macro
            ),
        )


SlotSpec = tuple[str, tuple[str, ...]]


def slot_param_name(slot_id: str) -> str:
    return f"{slot_id}_addr"


def keys_slot_specs(
    keys: Sequence[str],
    slot_prefix: str,
    node: SynthesizedNode,
    index: RegModelIndex,
) -> tuple[SlotSpec, ...]:
    """按节点上逻辑键共址关系拆成命名槽；与路径字符串无关。"""
    reg_paths_order: list[str] = []
    keys_by_reg: dict[str, list[str]] = {}
    for key in keys:
        ref = index.resolve(
            node.regs[key],
            ctx=f"program node {node.name!r} regs[{key!r}]",
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


def unique_slot_specs_in_order(
    slot_specs: tuple[SlotSpec, ...],
) -> tuple[SlotSpec, ...]:
    seen: set[str] = set()
    ordered: list[SlotSpec] = []
    for spec in slot_specs:
        slot_id = spec[0]
        if slot_id in seen:
            continue
        seen.add(slot_id)
        ordered.append(spec)
    return tuple(ordered)


def slot_id_for_reg_key(
    key: str,
    slot_specs: tuple[SlotSpec, ...],
) -> str:
    for slot_id, keys in slot_specs:
        if key in keys:
            return slot_id
    raise ValueError(f"program 逻辑键 {key!r} 不在 slot_specs 中")


def group_reg_write_templates(
    index: RegModelIndex,
    template_node: SynthesizedNode,
    keys: Sequence[str],
    *,
    slot_id: str,
    value_expr_for_key,
    comment_for_key,
) -> tuple[WriteTemplate, ...]:
    """按 YAML 逻辑键顺序分组，同物理寄存器多 field 合并为一次写。"""
    groups: list[tuple[str, list[WritePartTemplate]]] = []
    for key in keys:
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"program node {template_node.name!r} regs[{key!r}]",
        )
        reg_path = ref.reg.path
        part = WritePartTemplate(
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
            WriteTemplate(
                slot_param_name(slot_id),
                tuple(parts),
                reg_path,
                slot_id,
            ),
        )
    return tuple(
        WriteTemplate(
            slot_param_name(f"{slot_id}_{idx}"),
            tuple(parts),
            reg_path,
            f"{slot_id}_{idx}",
        )
        for idx, (reg_path, parts) in enumerate(groups)
    )


def _slot_macro_maps(
    nodes: Sequence[SynthesizedNode],
    index: RegModelIndex,
    slot_specs: tuple[SlotSpec, ...],
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    slot_order = tuple(slot_id for slot_id, _ in slot_specs)
    maps: list[dict[str, str]] = []
    for node in nodes:
        macros: dict[str, str] = {}
        for slot_id, keys in slot_specs:
            ref = index.resolve(
                node.regs[keys[0]],
                ctx=f"program node {node.name!r} regs[{keys[0]!r}]",
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


def _consolidate_program_addr_params(
    variant: str,
    write_templates: tuple[WriteTemplate, ...],
    nodes: Sequence[SynthesizedNode],
    index: RegModelIndex,
    slot_specs: tuple[SlotSpec, ...],
) -> tuple[tuple[WriteTemplate, ...], tuple[str, ...], tuple[str, ...]]:
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
            rep_to_param[rep] = f"{variant}_addr"
        else:
            rep_to_param[rep] = slot_param_name(rep)

    remapped: list[WriteTemplate] = []
    for wt in write_templates:
        rep = slot_to_rep[wt.slot_id]
        remapped.append(
            WriteTemplate(
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
) -> tuple[ValueBranch, ...]:
    branches: list[ValueBranch] = []
    for freq_hz in sorted(cfg_by_freq):
        cfg = cfg_by_freq[freq_hz]
        assignments = tuple(
            (reg_key_to_c_ident(name), cfg[name]) for name in cfg_logical_keys
        )
        branches.append(ValueBranch(freq_hz=freq_hz, assignments=assignments))
    return tuple(branches)


def _instance_addr_args_by_slots(
    node: SynthesizedNode,
    index: RegModelIndex,
    addr_param_slot_ids: Sequence[str],
    slot_specs: tuple[SlotSpec, ...],
) -> tuple[str, ...]:
    slot_to_keys = {slot_id: keys for slot_id, keys in slot_specs}
    args: list[str] = []
    for slot_id in addr_param_slot_ids:
        keys = slot_to_keys.get(slot_id)
        if keys is None:
            raise ValueError(
                f"program 节点 {node.name!r} 写槽 {slot_id!r} 与型号模板不一致"
            )
        ref = index.resolve(
            node.regs[keys[0]],
            ctx=f"program node {node.name!r} regs[{keys[0]!r}]",
        )
        args.append(ref.reg.addr_macro)
    return tuple(args)


def _collect_configured_program_nodes(
    candidates: Sequence[NodeBase],
    resolved: TreeResolve,
) -> list[SynthesizedNode]:
    nodes: list[SynthesizedNode] = []
    for node in candidates:
        if not isinstance(node, SynthesizedNode) or not node.regs:
            continue
        if resolved.by_name[node.name].values[node.configuration_key]:
            nodes.append(node)
    return nodes


def build_program(
    nodes: Sequence[NodeBase],
    index: RegModelIndex,
    resolved: TreeResolve,
) -> ProgramBundle:
    groups = {}
    layouts = {}
    configurations = {}
    for node in _collect_configured_program_nodes(nodes, resolved):
        state = resolved.by_name[node.name]
        cfg = state.values[node.configuration_key]
        fields = []
        keys_by_register = {}
        with node_context(node, "plan"):
            for key in sorted(node.regs):
                ctx = f"nodes[{node.name!r}].regs.{key}"
                ref = index.resolve(node.regs[key], ctx=ctx)
                if key in cfg:
                    validate_field_value(ref, cfg[key], ctx=ctx)
                fields.append((key, ref.effective_lsb, ref.effective_width))
                keys_by_register.setdefault(ref.reg.path, set()).add(key)
        layout = (
            tuple(fields),
            frozenset(frozenset(keys) for keys in keys_by_register.values()),
        )
        subgroup = 1
        group_key = (node.program_variant, subgroup)
        while group_key in groups:
            previous = configurations[group_key].get(state.resolved_freq)
            if layout == layouts[group_key] and (previous is None or previous == cfg):
                break
            subgroup += 1
            group_key = (node.program_variant, subgroup)
        groups.setdefault(group_key, []).append(node)
        layouts.setdefault(group_key, layout)
        configurations.setdefault(group_key, {})[state.resolved_freq] = cfg

    kind_plans: list[FunctionPlan] = []
    instances: list[InstancePlan] = []

    for group_key in sorted(groups.keys()):
        nodes = groups[group_key]
        variant, subgroup = group_key
        cfg_by_freq = configurations[group_key]
        template_node = nodes[0]
        slot_specs = unique_slot_specs_in_order(template_node.slot_specs(index))
        write_templates_raw = template_node.write_templates(index)
        write_templates, addr_params, addr_param_slot_ids = (
            _consolidate_program_addr_params(
                variant, write_templates_raw, nodes, index, slot_specs
            )
        )
        cfg_logical_keys = template_node.configuration_keys(cfg_by_freq)
        cfg_var_names = tuple(reg_key_to_c_ident(name) for name in cfg_logical_keys)
        fn_name = (template_node.function_prefix + variant) + (
            f"_{subgroup}" if subgroup > 1 else ""
        )
        kind_plans.append(
            FunctionPlan(
                fn_name=fn_name,
                addr_params=addr_params,
                cfg_var_names=cfg_var_names,
                freq_branches=_freq_branches(cfg_by_freq, cfg_logical_keys),
                write_templates=write_templates,
            )
        )
        for node in nodes:
            ready_addr_macro, ready_mask_hex = node.ready_view(index)
            node_slot_specs = unique_slot_specs_in_order(node.slot_specs(index))
            if node_slot_specs != slot_specs:
                raise ValueError(
                    f"variant {variant!r} 节点 {node.name!r} 写槽与模板不一致"
                )
            instances.append(
                InstancePlan(
                    node_name=node.name,
                    fn_name=fn_name,
                    addr_args=_instance_addr_args_by_slots(
                        node, index, addr_param_slot_ids, slot_specs
                    ),
                    freq_hz=resolved.by_name[node.name].resolved_freq,
                    poll_ready=True,
                    poll_function=node.poll_function,
                    poll_parameter=node.poll_parameter,
                    ready_addr_macro=ready_addr_macro,
                    ready_mask_hex=ready_mask_hex,
                )
            )

    return ProgramBundle(
        function_plans=tuple(kind_plans),
        instances=tuple(instances),
    )

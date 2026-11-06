from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Sequence, Protocol

from model.nodes import ExtraRegEntry, Tree
from node.errors import node_context
from .resolve import TreeResolve
from load.regmodel import (
    FieldRef,
    Reg,
    RegModelIndex,
    field_part_label,
    pack_field_value,
    validate_field_value,
)


@dataclass(frozen=True)
class FieldPartView:
    """Single field value fragment for one register write."""

    field_name: str
    part_label: str
    lsb: int
    width: int
    value: int
    comment: str

    @property
    def c_value_expr(self) -> str:
        """按旧版风格保留字段值与位移，不添加数字后缀。"""
        literal = f"0x{self.value:X}"
        return f"({literal:<6} << {self.lsb:<4})"


@dataclass(frozen=True)
class RegWriteStep:
    """One register write in the generated configuration sequence."""

    node_name: str
    reg: Reg
    value: int
    comment: str
    parts: tuple[FieldPartView, ...]
    step_index: int
    addr_pad_width: int = 0

    @property
    def addr_macro(self) -> str:
        return self.reg.addr_macro

    @property
    def c_config_step_lines(self) -> str:
        """按字段拼接寄存器初值，保留位移与注释对齐。"""
        pad = self.addr_pad_width if self.addr_pad_width > 0 else len(self.addr_macro)
        base_indent = "    "
        addr_field = "{ " + f"{self.addr_macro:<{pad}}" + ", "
        field_start_col = len(base_indent) + len(addr_field)
        cont_indent = " " * field_start_col
        lines = []
        for idx, part in enumerate(self.parts):
            prefix = base_indent + addr_field if idx == 0 else cont_indent
            sep = " |" if idx + 1 < len(self.parts) else " },"
            lines.append(f"{prefix}{part.c_value_expr}{sep} // {part.comment}")
        return "\n".join(lines)


def _is_single_bit_mask_hex(mask_hex: str) -> bool:
    literal = mask_hex.rstrip("uU")
    value = int(literal, 16)
    return value != 0 and (value & (value - 1)) == 0


@dataclass(frozen=True)
class ConfigPlan:
    function_plans: tuple[object, ...]
    instances: tuple[object, ...]
    steps: tuple[RegWriteStep, ...]

    @property
    def has_wait_lock_instances(self) -> bool:
        return any(inst.wait_lock for inst in self.instances)

    @property
    def fixed_wait_lock_mask_hex(self) -> str | None:
        """若全部须等待锁定的 PLL 共用同一单比特 mask，返回该字面量；否则为 None。"""
        masks = {inst.lock_mask_hex for inst in self.instances if inst.wait_lock}
        if len(masks) != 1:
            return None
        mask_hex = masks.pop()
        if not _is_single_bit_mask_hex(mask_hex):
            return None
        return mask_hex


@dataclass
class _FieldPatch:
    """Pending field assignment before register-level merge."""

    node_name: str
    field_ref: FieldRef
    value: int
    note: str


class SettingsView(Protocol):
    """Read-only access to settings declared by plugins."""

    def __getattr__(self, name: str) -> object: ...


def _patch(
    index: RegModelIndex,
    *,
    node_name: str,
    raw_path: str,
    value: int,
    note: str,
) -> _FieldPatch:
    ref = index.resolve(raw_path, ctx=f"node {node_name!r}")
    validate_field_value(ref, value, ctx=f"nodes[{node_name!r}] {raw_path}")
    return _FieldPatch(
        node_name=node_name,
        field_ref=ref,
        value=value,
        note=note,
    )


def _extra_reg_patch(
    index: RegModelIndex,
    entry: ExtraRegEntry,
    *,
    idx: int,
) -> _FieldPatch:
    ref = index.resolve(entry.path, ctx=f"extra_regs[{idx}].path")
    max_val = (1 << ref.effective_width) - 1
    if entry.value < 0 or entry.value > max_val:
        raise ValueError(
            f"extra_regs[{idx}].value {entry.value} 超出路径 {entry.path!r} "
            f"可写范围 0..{max_val}"
        )
    return _FieldPatch(
        node_name="extra_regs",
        field_ref=ref,
        value=entry.value,
        note=f"{entry.path}={entry.value}",
    )


def _patch_to_part_view(patch: _FieldPatch) -> FieldPartView:
    ref = patch.field_ref
    label = field_part_label(ref.field, ref.offset, ref.width)
    note = patch.note.strip() if patch.note else ""
    if note:
        comment = note
    else:
        comment = f"{patch.node_name} {ref.reg.path}.{label}"
    return FieldPartView(
        field_name=ref.field.name,
        part_label=label,
        lsb=ref.effective_lsb,
        width=ref.effective_width,
        value=patch.value & ((1 << ref.effective_width) - 1),
        comment=comment,
    )


def merge_field_patches(patches: List[_FieldPatch]) -> List[RegWriteStep]:
    """把 field 赋值合并为按 32 位寄存器的一次写。

    同一寄存器的多个 field 即使中间夹了其它寄存器，也合并到首次出现的位置。
    同一 field 再次赋值时，后写值覆盖前写值。
    """
    if not patches:
        return []

    by_reg: dict[str, list[_FieldPatch]] = {}
    for patch in patches:
        by_reg.setdefault(patch.field_ref.reg.path, []).append(patch)

    steps = []
    for group in by_reg.values():
        first_patch = group[0]
        value = 0
        part_views_by_key: dict[tuple[str, int, int], FieldPartView] = {}
        notes: dict[str, None] = {}
        for patch in group:
            ref = patch.field_ref
            part_key = (ref.field.name, ref.effective_lsb, ref.effective_width)
            value = pack_field_value(value, ref, patch.value)
            part_views_by_key[part_key] = _patch_to_part_view(patch)
            if patch.note:
                notes[patch.note] = None
        steps.append(
            RegWriteStep(
                node_name=first_patch.node_name,
                reg=first_patch.field_ref.reg,
                value=value,
                comment="; ".join(notes) if notes else first_patch.node_name,
                parts=tuple(sorted(part_views_by_key.values(), key=lambda part: part.lsb)),
                step_index=0,
            )
        )
    return steps


def _with_step_indexes(steps: List[RegWriteStep]) -> tuple[RegWriteStep, ...]:
    pad = max((len(s.addr_macro) for s in steps), default=0)
    return tuple(
        replace(step, step_index=idx, addr_pad_width=pad)
        for idx, step in enumerate(steps)
    )


@dataclass(frozen=True)
class HeaderRegAddress:
    """C 头文件中单个寄存器地址宏。"""

    reg: Reg
    addr_expr: str


@dataclass(frozen=True)
class HeaderAddressPlan:
    """pll_mini.h 地址宏生成计划。"""

    reg_base_macro: str
    reg_base_hex: str
    regs: tuple[HeaderRegAddress, ...]


def global_reg_base_macro(header_guard: str) -> str:
    """由头文件 guard 名推导全局寄存器基址宏名。"""
    if header_guard.endswith("_H"):
        return f"{header_guard[:-2]}_REG_BASE"
    return f"{header_guard}_REG_BASE"


def build_header_address_plan(
    regs: Sequence[Reg],
    *,
    reg_base_offset: int,
    header_guard: str,
) -> HeaderAddressPlan:
    """全局基址宏 + 各寄存器地址，地址为基址与 RALF 偏移常量之和。"""
    reg_base_macro = global_reg_base_macro(header_guard)
    reg_base_hex = f"0x{reg_base_offset:X}"
    if not regs:
        return HeaderAddressPlan(reg_base_macro, reg_base_hex, ())

    header_regs = tuple(
        HeaderRegAddress(
            reg=reg,
            addr_expr=f"{reg_base_macro} + 0x{reg.address:X}",
        )
        for reg in sorted(
            regs,
            key=lambda item: (item.address, item.addr_macro, item.path),
        )
    )
    return HeaderAddressPlan(reg_base_macro, reg_base_hex, header_regs)


def collect_used_regs(
    index: RegModelIndex,
    plan: ConfigPlan,
    *,
    extra_regs: Sequence[Reg] = (),
) -> tuple[Reg, ...]:
    """Collect registers referenced by generated C configuration code."""
    by_path: dict[str, Reg] = {}
    macro_to_reg = {reg.addr_macro: reg for reg in index.regs}
    for step in plan.steps:
        by_path[step.reg.path] = step.reg
    for inst in plan.instances:
        for macro in (*inst.addr_args, inst.lock_addr_macro):
            if not macro:
                continue
            reg = macro_to_reg.get(macro)
            if reg is None:
                raise ValueError(f"未知地址宏 {macro!r}")
            by_path[reg.path] = reg
    for reg in extra_regs:
        by_path[reg.path] = reg
    return tuple(reg for reg in index.regs if reg.path in by_path)


def build_config_plan(
    tree: Tree,
    index: RegModelIndex,
    settings: SettingsView,
    resolved: TreeResolve,
    extra_regs: Sequence[ExtraRegEntry] = (),
) -> ConfigPlan:
    """Build PLL kind plans, instances, and non-PLL register write steps."""
    nodes = tree.nodes_ordered
    groups = {}
    for node in nodes:
        if node.plan_group:
            groups.setdefault(node.plan_group, node)
    bundles = []
    for node in groups.values():
        with node_context(node, "plan"):
            bundles.append(node.build_plan_group(nodes, index, resolved))
    dev_patches: List[_FieldPatch] = []
    for node in sorted(nodes, key=lambda item: item.plan_priority):
        with node_context(node, "plan"):
            dev_patches.extend(
                node.plan_patches(index, settings, resolved.by_name[node.name])
            )

    dev_reg_paths = {patch.field_ref.reg.path for patch in dev_patches}
    extra_only_patches: List[_FieldPatch] = []
    extra_shared_patches: List[_FieldPatch] = []
    for idx, entry in enumerate(extra_regs):
        patch = _extra_reg_patch(index, entry, idx=idx)
        if patch.field_ref.reg.path in dev_reg_paths:
            extra_shared_patches.append(patch)
        else:
            extra_only_patches.append(patch)

    patches = [*extra_only_patches, *dev_patches, *extra_shared_patches]

    return ConfigPlan(
        function_plans=tuple(
            item for bundle in bundles if bundle for item in bundle.function_plans
        ),
        instances=tuple(
            item for bundle in bundles if bundle for item in bundle.instances
        ),
        steps=_with_step_indexes(merge_field_patches(patches)),
    )

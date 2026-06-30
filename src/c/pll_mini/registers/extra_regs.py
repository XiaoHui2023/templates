from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from load.regmodel import Reg, RegModelIndex, field_part_label, reg_bound_max
from .pll_kind_plan import PllWritePartTemplate, PllWriteTemplate
from .plan import _FieldPatch


@dataclass(frozen=True)
class ExtraRegWrite:
    """单步额外寄存器读改写。"""

    reg: Reg
    addr_macro: str
    template: PllWriteTemplate


@dataclass(frozen=True)
class ExtraRegPlan:
    """配置流程末尾调用的额外寄存器写计划。"""

    fn_name: str
    writes: tuple[ExtraRegWrite, ...]


def _extra_slot_id(reg: Reg, step_idx: int) -> str:
    base = f"extra_{reg.macro_prefix.lower()}"
    if step_idx == 0:
        return base
    return f"{base}_{step_idx}"


def _group_extra_reg_patches(
    items: Sequence[tuple[_FieldPatch, bool]],
) -> list[list[_FieldPatch]]:
    """按列表顺序分组：同寄存器连续项合并；solo 为真时单独成组。"""
    groups: list[list[_FieldPatch]] = []
    current: list[_FieldPatch] = []

    def flush() -> None:
        nonlocal current
        if current:
            groups.append(current)
            current = []

    for patch, solo in items:
        if solo:
            flush()
            groups.append([patch])
            continue
        if not current:
            current = [patch]
            continue
        if patch.field_ref.reg.path == current[-1].field_ref.reg.path:
            current.append(patch)
        else:
            flush()
            current = [patch]
    flush()
    return groups


def build_extra_reg_plan(
    entries: Sequence[object],
    index: RegModelIndex,
    *,
    fn_name: str = "pll_mini_config_extra_regs",
) -> ExtraRegPlan | None:
    """把 extra_regs 列表展开为按顺序、可合并的读改写写序列。"""
    if not entries:
        return None

    items: list[tuple[_FieldPatch, bool]] = []
    for idx, entry in enumerate(entries):
        path = entry.path
        value = entry.value
        solo = bool(getattr(entry, "solo", False))
        ctx = f"tree.extra_regs[{idx}].path"
        ref = index.resolve(path, ctx=ctx)
        max_val = reg_bound_max(ref)
        if value < 0 or value > max_val:
            raise ValueError(
                f"tree.extra_regs[{idx}].value {value} 超出路径 {path!r} "
                f"可写范围 0..{max_val}"
            )
        items.append(
            (
                _FieldPatch(
                    node_name="extra",
                    field_ref=ref,
                    value=value,
                    note=f"{path}={value}",
                ),
                solo,
            )
        )

    writes: list[ExtraRegWrite] = []
    reg_step_idx: dict[str, int] = {}

    for group in _group_extra_reg_patches(items):
        reg_path = group[0].field_ref.reg.path
        part_keys: set[tuple[str, int, int]] = set()
        parts: list[PllWritePartTemplate] = []
        reg = group[0].field_ref.reg
        for patch in group:
            ref = patch.field_ref
            part_key = (ref.field.name, ref.effective_lsb, ref.effective_width)
            if part_key in part_keys:
                label = field_part_label(ref.field, ref.offset, ref.width)
                raise ValueError(
                    f"tree.extra_regs 对寄存器 {reg_path!r} 的 field "
                    f"{label!r} 重复配置"
                )
            part_keys.add(part_key)
            parts.append(
                PllWritePartTemplate(
                    ref.effective_lsb,
                    ref.effective_width,
                    str(patch.value),
                    patch.note,
                )
            )
        step_idx = reg_step_idx.get(reg_path, 0)
        reg_step_idx[reg_path] = step_idx + 1
        slot_id = _extra_slot_id(reg, step_idx)
        template = PllWriteTemplate(
            f"{slot_id}_addr",
            tuple(parts),
            reg_path,
            slot_id,
        )
        writes.append(
            ExtraRegWrite(reg=reg, addr_macro=reg.addr_macro, template=template)
        )

    return ExtraRegPlan(fn_name=fn_name, writes=tuple(writes))

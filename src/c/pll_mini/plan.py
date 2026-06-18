from __future__ import annotations

from dataclasses import dataclass
from typing import List

from formulas import dto_ratio_to_step
from nodes import DivNode, DtoNode, GateNode, MuxNode, PllNode, Tree
from resolve import ResolvedNode, TreeResolve
from regmodel import (
    FieldRef,
    Reg,
    RegModelIndex,
    field_part_label,
    pack_field_value,
)
from reg_paths import inno_postdiv_reg_keys

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
    def value_u(self) -> str:
        return f"{self.value}u"

    @property
    def lsb_u(self) -> str:
        return f"{self.lsb}u"

    @property
    def value_hex_lit(self) -> str:
        return f"0x{self.value:X}"


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
    def value_hex(self) -> str:
        return f"0x{self.value & 0xFFFFFFFF:08X}u"

    def _packed_value_lines(
        self,
        *,
        first_prefix: str,
        cont_indent: str,
        close: str,
        unsigned_suffix: bool = True,
        cast_uint32: bool = True,
        hex_literals: bool = False,
    ) -> list[str]:
        lines: list[str] = []
        for idx, part in enumerate(self.parts):
            if idx == 0:
                prefix = first_prefix
            else:
                prefix = cont_indent
            sep = " |" if idx + 1 < len(self.parts) else close
            if hex_literals:
                value_lit = part.value_hex_lit
                lsb_lit = str(part.lsb)
            elif unsigned_suffix:
                value_lit = part.value_u
                lsb_lit = part.lsb_u
            else:
                value_lit = str(part.value)
                lsb_lit = str(part.lsb)
            if cast_uint32:
                expr = f"((uint32_t){value_lit:<6} << {lsb_lit:<4})"
            else:
                expr = f"({value_lit:<6} << {lsb_lit:<4})"
            lines.append(f"{prefix}{expr}{sep} // {part.comment}")
        return lines

    @property
    def c_config_step_lines(self) -> str:
        pad = self.addr_pad_width if self.addr_pad_width > 0 else len(self.addr_macro)
        base_indent = "    "
        addr_field = "{ " + f"{self.addr_macro:<{pad}}" + ", "
        field_start_col = len(base_indent) + len(addr_field)
        cont_indent = " " * field_start_col
        return "\n".join(
            self._packed_value_lines(
                first_prefix=base_indent + addr_field,
                cont_indent=cont_indent,
                close=" },",
                unsigned_suffix=False,
                cast_uint32=False,
                hex_literals=True,
            )
        )


def _is_single_bit_mask_hex(mask_hex: str) -> bool:
    literal = mask_hex.rstrip("uU")
    value = int(literal, 16)
    return value != 0 and (value & (value - 1)) == 0


@dataclass(frozen=True)
class ConfigPlan:
    pll_kind_plans: tuple["PllKindPlan", ...]
    pll_instances: tuple["PllInstancePlan", ...]
    dev_steps: tuple[RegWriteStep, ...]

    @property
    def pll_writes(self) -> tuple["PllInstancePlan", ...]:
        return self.pll_instances

    @property
    def fixed_wait_lock_mask_hex(self) -> str | None:
        """若全部须等待锁定的 PLL 共用同一单比特 mask，返回该字面量；否则为 None。"""
        masks = {
            inst.lock_mask_hex
            for inst in self.pll_instances
            if inst.wait_lock
        }
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


PLL_SC_PD_KEYS = ("vocpd", "postdivpd", "dsmpd", "pd", "bypass")
PLL_SC_DIV_KEYS = ("refdiv", "postdiv2", "postdiv1", "fbdiv")

PLL_TCI_CTRL_KEYS = ("bypass", "pwrdn", "reset")
PLL_TCI_DIV_KEYS = ("clkod", "clkf", "clkr", "bwadj")

PLL_DW_ORDER = (
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
)

PLL_INNO_SHARED_KEYS = ("pd", "refdiv", "fbdiv")


class SettingsView:
    """Read-only settings view used while building the plan."""

    def __init__(
        self,
        *,
        gate_reg_high_means_open: bool,
        div_reg_high_means_reset: bool,
        dto_reg_high_means_reset: bool,
    ) -> None:
        self.gate_reg_high_means_open = gate_reg_high_means_open
        self.div_reg_high_means_reset = div_reg_high_means_reset
        self.dto_reg_high_means_reset = dto_reg_high_means_reset


def _patch(
    index: RegModelIndex,
    *,
    node_name: str,
    raw_path: str,
    value: int,
    note: str,
) -> _FieldPatch:
    ref = index.resolve(raw_path, ctx=f"node {node_name!r}")
    return _FieldPatch(
        node_name=node_name,
        field_ref=ref,
        value=value,
        note=note,
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
        value=patch.value,
        comment=comment,
    )


def merge_field_patches(patches: List[_FieldPatch]) -> List[RegWriteStep]:
    """把 field 赋值合并为按 32 位寄存器的一次写。

    同一寄存器、同一轮写序 epoch 内的多个 field，即使中间夹了其它寄存器，
    也合并到该 epoch 首次出现的位置。同一 field 再次赋值则开启新 epoch。
    """
    if not patches:
        return []

    reg_part_keys: dict[str, set[tuple[str, int, int]]] = {}
    reg_epochs: dict[str, list[list[tuple[int, _FieldPatch]]]] = {}

    for idx, patch in enumerate(patches):
        ref = patch.field_ref
        reg_path = ref.reg.path
        part_key = (ref.field.name, ref.effective_lsb, ref.effective_width)

        if reg_path not in reg_epochs:
            reg_epochs[reg_path] = [[]]
            reg_part_keys[reg_path] = set()

        if part_key in reg_part_keys[reg_path]:
            reg_epochs[reg_path].append([])
            reg_part_keys[reg_path] = set()

        reg_epochs[reg_path][-1].append((idx, patch))
        reg_part_keys[reg_path].add(part_key)

    steps_with_idx: list[tuple[int, RegWriteStep]] = []
    last_written: dict[str, int] = {}

    for epochs in reg_epochs.values():
        for epoch in epochs:
            if not epoch:
                continue
            earliest_idx = epoch[0][0]
            first_patch = epoch[0][1]
            reg = first_patch.field_ref.reg
            value = last_written.get(reg.path, 0)
            part_views_by_key: dict[tuple[str, int, int], FieldPartView] = {}
            notes: list[str] = []

            for _patch_idx, patch in epoch:
                ref = patch.field_ref
                part_key = (ref.field.name, ref.effective_lsb, ref.effective_width)
                value = pack_field_value(value, ref, patch.value)
                part_views_by_key[part_key] = _patch_to_part_view(patch)
                if patch.note:
                    notes.append(patch.note)

            part_views = sorted(part_views_by_key.values(), key=lambda part: part.lsb)
            last_written[reg.path] = value
            unique_notes = list(dict.fromkeys(notes))
            comment = (
                "; ".join(unique_notes) if unique_notes else first_patch.node_name
            )
            steps_with_idx.append(
                (
                    earliest_idx,
                    RegWriteStep(
                        node_name=first_patch.node_name,
                        reg=reg,
                        value=value,
                        comment=comment,
                        parts=tuple(part_views),
                        step_index=0,
                    ),
                )
            )

    steps_with_idx.sort(key=lambda item: item[0])
    return [step for _idx, step in steps_with_idx]


def _reset_release_patch(
    index: RegModelIndex,
    node: DivNode | DtoNode,
    *,
    high_means_reset: bool,
) -> _FieldPatch:
    release_val = 0 if high_means_reset else 1
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.regs["rst"],
        value=release_val,
        note=f"{node.name} rst release",
    )


def _expand_pll_sc(
    index: RegModelIndex,
    node: PllNode,
    cfg: dict[str, int],
) -> List[_FieldPatch]:
    patches: List[_FieldPatch] = []
    pd_down = f"{node.name} power-down"
    for key in PLL_SC_PD_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=1,
                note=pd_down if key == PLL_SC_PD_KEYS[0] else "",
            )
        )
    div_note = (
        f"{node.name} fbdiv={cfg['fbdiv']} refdiv={cfg['refdiv']} "
        f"postdiv1={cfg['postdiv1']} postdiv2={cfg['postdiv2']}"
    )
    for key in PLL_SC_DIV_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=cfg[key],
                note=div_note if key == PLL_SC_DIV_KEYS[0] else "",
            )
        )
    en_note = f"{node.name} enable"
    for key in PLL_SC_PD_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=cfg[key],
                note=en_note if key == PLL_SC_PD_KEYS[0] else "",
            )
        )
    return patches


def _expand_pll_tci(
    index: RegModelIndex,
    node: PllNode,
    cfg: dict[str, int],
) -> List[_FieldPatch]:
    patches: List[_FieldPatch] = []
    ctrl_note = (
        f"{node.name} bypass=1 pwrdn=0 reset=1"
    )
    for key, val in zip(
        PLL_TCI_CTRL_KEYS, (1, 0, 1), strict=True
    ):
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=val,
                note=ctrl_note if key == PLL_TCI_CTRL_KEYS[0] else "",
            )
        )
    div_note = (
        f"{node.name} clkod={cfg['clkod']} clkf={cfg['clkf']} "
        f"clkr={cfg['clkr']} bwadj={cfg['bwadj']}"
    )
    for key in PLL_TCI_DIV_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=cfg[key],
                note=div_note if key == PLL_TCI_DIV_KEYS[0] else "",
            )
        )
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["reset"],
            value=0,
            note=f"{node.name} reset release",
        )
    )
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["bypass"],
            value=0,
            note=f"{node.name} bypass off",
        )
    )
    return patches


def _expand_pll_dw(
    index: RegModelIndex,
    node: PllNode,
    cfg: dict[str, int],
) -> List[_FieldPatch]:
    note = (
        f"{node.name} fbdiv={cfg['fbdiv']} prediv={cfg['prediv']} "
        f"divvcop={cfg['divvcop']}"
    )
    return [
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs[key],
            value=cfg[key],
            note=note if key == PLL_DW_ORDER[0] else "",
        )
        for key in PLL_DW_ORDER
    ]


def _expand_pll_inno(
    index: RegModelIndex,
    node: PllNode,
    cfg: dict[str, int],
) -> List[_FieldPatch]:
    patches: List[_FieldPatch] = []
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["pd"],
            value=1,
            note=f"{node.name} pd assert",
        )
    )
    shared = (
        f"{node.name} refdiv={cfg['refdiv']} fbdiv={cfg['fbdiv']}"
    )
    for key in ("refdiv", "fbdiv"):
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=cfg[key],
                note=shared if key == "refdiv" else "",
            )
        )
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["pd"],
            value=0,
            note=f"{node.name} pd release",
        )
    )
    if node.output_count <= 1:
        post = (
            f"{node.name} postdiv1={cfg['postdiv1']} "
            f"postdiv2={cfg['postdiv2']}"
        )
        for key in ("postdiv1", "postdiv2"):
            patches.append(
                _patch(
                    index,
                    node_name=node.name,
                    raw_path=node.regs[key],
                    value=cfg[key],
                    note=post if key == "postdiv1" else "",
                )
            )
        return patches
    for group_id in range(node.output_count):
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        post = (
            f"{node.name} out{group_id} postdiv1={cfg[p1_key]} "
            f"postdiv2={cfg[p2_key]}"
        )
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[p1_key],
                value=cfg[p1_key],
                note=post,
            )
        )
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[p2_key],
                value=cfg[p2_key],
                note="",
            )
        )
    return patches


def expand_pll_patches(
    index: RegModelIndex,
    node: PllNode,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    cfg = resolved.pll_cfg
    if node.pll_kind == "sc":
        return _expand_pll_sc(index, node, cfg)
    if node.pll_kind == "tci":
        return _expand_pll_tci(index, node, cfg)
    if node.pll_kind == "dw":
        return _expand_pll_dw(index, node, cfg)
    if node.pll_kind == "inno":
        return _expand_pll_inno(index, node, cfg)
    raise ValueError(f"unknown pll_kind {node.pll_kind!r}")


def expand_div_patches(
    index: RegModelIndex,
    node: DivNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    from formulas import div_ratio_to_n

    patches = [
        _reset_release_patch(
            index,
            node,
            high_means_reset=settings.div_reg_high_means_reset,
        )
    ]
    div_n = div_ratio_to_n(resolved.ratio)
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["div"],
            value=div_n,
            note=f"{node.name} ratio={resolved.ratio} div={div_n}",
        )
    )
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["load"],
            value=1,
            note=f"{node.name} load",
        )
    )
    return patches


def expand_dto_patches(
    index: RegModelIndex,
    node: DtoNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    step = dto_ratio_to_step(resolved.ratio)
    patches = [
        _reset_release_patch(
            index,
            node,
            high_means_reset=settings.dto_reg_high_means_reset,
        )
    ]
    dto_note = (
        f"{node.name} ratio={resolved.ratio} load=1 bypass=0 step={step}"
    )
    for key, val in zip(
        ("load", "bypass", "step"), (1, 0, step), strict=True
    ):
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=val,
                note=dto_note if key == "load" else "",
            )
        )
    return patches


def expand_gate_patch(
    index: RegModelIndex,
    node: GateNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> _FieldPatch:
    if settings.gate_reg_high_means_open:
        value = 1 if resolved.gate_open else 0
    else:
        value = 0 if resolved.gate_open else 1
    state = "open" if resolved.gate_open else "close"
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.reg,
        value=value,
        note=f"{node.name} gate {state}",
    )


def expand_mux_patch(
    index: RegModelIndex,
    node: MuxNode,
    resolved: ResolvedNode,
) -> _FieldPatch:
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.reg,
        value=resolved.mux_sel,
        note=f"{node.name} mux sel={resolved.mux_sel}",
    )


def _pll_lock_view(
    index: RegModelIndex,
    node: PllNode,
) -> tuple[str, str]:
    if "lock" not in node.regs:
        raise ValueError(f"pll node {node.name!r} requires regs.lock")
    ref = index.resolve(node.regs["lock"], ctx=f"node {node.name!r} lock")
    mask_hex = f"0x{ref.effective_mask & 0xFFFFFFFF:08X}u"
    return ref.reg.addr_macro, mask_hex


def _pll_fn_name(node_name: str) -> str:
    return f"pll_mini_config_{node_name}"


def _with_step_indexes(steps: List[RegWriteStep]) -> tuple[RegWriteStep, ...]:
    indexed: list[RegWriteStep] = []
    for idx, step in enumerate(steps):
        indexed.append(
            RegWriteStep(
                node_name=step.node_name,
                reg=step.reg,
                value=step.value,
                comment=step.comment,
                parts=step.parts,
                step_index=idx,
            )
        )
    pad = max((len(s.addr_macro) for s in indexed), default=0)
    return tuple(
        RegWriteStep(
            node_name=s.node_name,
            reg=s.reg,
            value=s.value,
            comment=s.comment,
            parts=s.parts,
            step_index=s.step_index,
            addr_pad_width=pad,
        )
        for s in indexed
    )


def collect_used_regs(
    index: RegModelIndex,
    plan: ConfigPlan,
) -> tuple[Reg, ...]:
    """Collect registers referenced by generated C configuration code."""
    by_path: dict[str, Reg] = {}
    macro_to_reg = {reg.addr_macro: reg for reg in index.regs}
    for step in plan.dev_steps:
        by_path[step.reg.path] = step.reg
    for inst in plan.pll_instances:
        for macro in (*inst.addr_args, inst.lock_addr_macro):
            if not macro:
                continue
            reg = macro_to_reg.get(macro)
            if reg is None:
                raise ValueError(f"未知地址宏 {macro!r}")
            by_path[reg.path] = reg
    return tuple(reg for reg in index.regs if reg.path in by_path)


def build_config_plan(
    tree: Tree,
    index: RegModelIndex,
    settings: SettingsView,
    resolved: TreeResolve,
) -> ConfigPlan:
    """Build PLL kind plans, instances, and non-PLL register write steps."""
    from pll_kind_plan import build_pll_plan

    pll_bundle = build_pll_plan(tree, index, resolved)
    dev_steps: List[RegWriteStep] = []

    for node in tree.nodes_ordered:
        state = resolved.by_name[node.name]
        if not state.active:
            continue
        if isinstance(node, DivNode) and node.regs:
            dev_steps.extend(
                merge_field_patches(
                    expand_div_patches(index, node, settings, state)
                )
            )
        elif isinstance(node, DtoNode) and node.regs:
            dev_steps.extend(
                merge_field_patches(
                    expand_dto_patches(index, node, settings, state)
                )
            )

    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and node.reg:
            state = resolved.by_name[node.name]
            if state.gate_open:
                dev_steps.extend(
                    merge_field_patches(
                        [expand_gate_patch(index, node, settings, state)]
                    )
                )

    for node in tree.nodes_ordered:
        if isinstance(node, MuxNode) and node.reg:
            state = resolved.by_name[node.name]
            if state.active:
                dev_steps.extend(
                    merge_field_patches(
                        [expand_mux_patch(index, node, state)]
                    )
                )

    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and node.reg:
            state = resolved.by_name[node.name]
            if not state.gate_open:
                dev_steps.extend(
                    merge_field_patches(
                        [expand_gate_patch(index, node, settings, state)]
                    )
                )

    return ConfigPlan(
        pll_kind_plans=pll_bundle.kind_plans,
        pll_instances=pll_bundle.instances,
        dev_steps=_with_step_indexes(dev_steps),
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

from nodes import DivNode, DtoNode, GateNode, MuxNode, PllNode, Tree
from regmodel import (
    FieldRef,
    Reg,
    RegModelIndex,
    field_part_label,
    pack_field_value,
)
from reg_paths import inno_postdiv_reg_keys

StepKind = Literal["write", "wait_lock"]


@dataclass(frozen=True)
class FieldPartView:
    """单个可编辑 field 切片；对应节点 reg 路径的最小粒度。"""

    field_name: str
    part_label: str
    lsb: int
    width: int
    value: int
    comment: str

    @property
    def value_hex(self) -> str:
        return f"0x{self.value & 0xFFFFFFFF:08X}u"


@dataclass(frozen=True)
class RegWriteStep:
    """整寄存器写入步骤。"""

    kind: StepKind
    node_name: str
    reg: Reg
    value: int
    comment: str
    parts: tuple[FieldPartView, ...]
    step_index: int

    @property
    def addr_macro(self) -> str:
        return self.reg.addr_macro

    @property
    def value_hex(self) -> str:
        return f"0x{self.value & 0xFFFFFFFF:08X}u"

    @property
    def parts_array_name(self) -> str:
        return f"pll_mini_step_{self.step_index}_fields"


@dataclass(frozen=True)
class WaitLockStep:
    """PLL lock 轮询步骤。"""

    kind: StepKind
    node_name: str
    reg: Reg
    lock_mask: int
    timeout_us: int
    comment: str

    @property
    def addr_macro(self) -> str:
        return self.reg.addr_macro

    @property
    def lock_mask_hex(self) -> str:
        return f"0x{self.lock_mask & 0xFFFFFFFF:08X}u"


ConfigStep = RegWriteStep | WaitLockStep


@dataclass
class _FieldPatch:
    """规划阶段的单次 field 赋值，供合并为整 reg 写。"""

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
    """plan 使用的 settings 只读视图。"""

    def __init__(
        self,
        *,
        gate_reg_high_means_open: bool,
        div_reg_high_means_reset: bool,
        dto_reg_high_means_reset: bool,
        lock_timeout_us: int,
    ) -> None:
        self.gate_reg_high_means_open = gate_reg_high_means_open
        self.div_reg_high_means_reset = div_reg_high_means_reset
        self.dto_reg_high_means_reset = dto_reg_high_means_reset
        self.lock_timeout_us = lock_timeout_us


def _patch(
    index: RegModelIndex,
    *,
    node_name: str,
    raw_path: str,
    value: int,
    note: str,
) -> _FieldPatch:
    ref = index.resolve(raw_path, ctx=f"节点 {node_name!r}")
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
    """把 field 级补丁按 reg 合并；同一 reg 内 field 重复赋值时分多次写。

    Args:
        patches: 按配置顺序排列的 field 赋值。

    Returns:
        整寄存器写入步骤。
    """
    out: List[RegWriteStep] = []
    last_written: dict[str, int] = {}
    idx = 0
    while idx < len(patches):
        first = patches[idx]
        reg = first.field_ref.reg
        value = last_written.get(reg.path, 0)
        touched: set[str] = set()
        notes: list[str] = []
        part_views: list[FieldPartView] = []
        start = idx
        while idx < len(patches) and patches[idx].field_ref.reg.path == reg.path:
            patch = patches[idx]
            ref = patch.field_ref
            part_key = (ref.field.name, ref.effective_lsb, ref.effective_width)
            if part_key in touched:
                break
            value = pack_field_value(value, ref, patch.value)
            touched.add(part_key)
            part_views.append(_patch_to_part_view(patch))
            if patch.note:
                notes.append(patch.note)
            idx += 1
        if idx == start:
            patch = patches[idx]
            value = pack_field_value(
                last_written.get(reg.path, 0),
                patch.field_ref,
                patch.value,
            )
            part_views = [_patch_to_part_view(patch)]
            if patch.note:
                notes = [patch.note]
            idx += 1
        last_written[reg.path] = value
        unique_notes = list(dict.fromkeys(notes))
        comment = "; ".join(unique_notes) if unique_notes else first.node_name
        out.append(
            RegWriteStep(
                kind="write",
                node_name=first.node_name,
                reg=reg,
                value=value,
                comment=comment,
                parts=tuple(part_views),
                step_index=0,
            )
        )
    return out


def _rst_pulse_patches(
    index: RegModelIndex,
    node: DivNode | DtoNode,
    *,
    high_means_reset: bool,
) -> List[_FieldPatch]:
    reset_val = 1 if high_means_reset else 0
    release_val = 0 if high_means_reset else 1
    path = node.regs["rst"]
    return [
        _patch(
            index,
            node_name=node.name,
            raw_path=path,
            value=reset_val,
            note=f"{node.name} rst assert",
        ),
        _patch(
            index,
            node_name=node.name,
            raw_path=path,
            value=release_val,
            note=f"{node.name} rst release",
        ),
    ]


def _load_pulse_patches(
    index: RegModelIndex,
    node: DivNode,
) -> List[_FieldPatch]:
    path = node.regs["load"]
    return [
        _patch(
            index,
            node_name=node.name,
            raw_path=path,
            value=0,
            note=f"{node.name} load deassert",
        ),
        _patch(
            index,
            node_name=node.name,
            raw_path=path,
            value=1,
            note=f"{node.name} load assert",
        ),
    ]


def _expand_pll_sc(index: RegModelIndex, node: PllNode) -> List[_FieldPatch]:
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
        f"{node.name} fbdiv={node.cfg['fbdiv']} refdiv={node.cfg['refdiv']} "
        f"postdiv1={node.cfg['postdiv1']} postdiv2={node.cfg['postdiv2']}"
    )
    for key in PLL_SC_DIV_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=node.cfg[key],
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
                value=node.cfg[key],
                note=en_note if key == PLL_SC_PD_KEYS[0] else "",
            )
        )
    return patches


def _expand_pll_tci(index: RegModelIndex, node: PllNode) -> List[_FieldPatch]:
    patches: List[_FieldPatch] = []
    ctrl_note = (
        f"{node.name} bypass={node.cfg['bypass']} pwrdn={node.cfg['pwrdn']} "
        f"reset={node.cfg['reset']}"
    )
    for key in PLL_TCI_CTRL_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=node.cfg[key],
                note=ctrl_note if key == PLL_TCI_CTRL_KEYS[0] else "",
            )
        )
    div_note = (
        f"{node.name} clkod={node.cfg['clkod']} clkf={node.cfg['clkf']} "
        f"clkr={node.cfg['clkr']} bwadj={node.cfg['bwadj']}"
    )
    for key in PLL_TCI_DIV_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=node.cfg[key],
                note=div_note if key == PLL_TCI_DIV_KEYS[0] else "",
            )
        )
    return patches


def _expand_pll_dw(index: RegModelIndex, node: PllNode) -> List[_FieldPatch]:
    note = (
        f"{node.name} fbdiv={node.cfg['fbdiv']} prediv={node.cfg['prediv']} "
        f"divvcop={node.cfg['divvcop']}"
    )
    return [
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs[key],
            value=node.cfg[key],
            note=note if key == PLL_DW_ORDER[0] else "",
        )
        for key in PLL_DW_ORDER
    ]


def _expand_pll_inno(index: RegModelIndex, node: PllNode) -> List[_FieldPatch]:
    patches: List[_FieldPatch] = []
    shared = (
        f"{node.name} refdiv={node.cfg['refdiv']} fbdiv={node.cfg['fbdiv']} "
        f"pd={node.cfg['pd']}"
    )
    for key in PLL_INNO_SHARED_KEYS:
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=node.cfg[key],
                note=shared if key == PLL_INNO_SHARED_KEYS[0] else "",
            )
        )
    if node.output_count <= 1:
        post = (
            f"{node.name} postdiv1={node.cfg['postdiv1']} "
            f"postdiv2={node.cfg['postdiv2']}"
        )
        for key in ("postdiv1", "postdiv2"):
            patches.append(
                _patch(
                    index,
                    node_name=node.name,
                    raw_path=node.regs[key],
                    value=node.cfg[key],
                    note=post if key == "postdiv1" else "",
                )
            )
        return patches
    for group_id in range(node.output_count):
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        post = (
            f"{node.name} out{group_id} postdiv1={node.cfg[p1_key]} "
            f"postdiv2={node.cfg[p2_key]}"
        )
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[p1_key],
                value=node.cfg[p1_key],
                note=post,
            )
        )
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[p2_key],
                value=node.cfg[p2_key],
                note="",
            )
        )
    return patches


def expand_pll_patches(index: RegModelIndex, node: PllNode) -> List[_FieldPatch]:
    if node.pll_kind == "sc":
        return _expand_pll_sc(index, node)
    if node.pll_kind == "tci":
        return _expand_pll_tci(index, node)
    if node.pll_kind == "dw":
        return _expand_pll_dw(index, node)
    if node.pll_kind == "inno":
        return _expand_pll_inno(index, node)
    raise ValueError(f"未知 pll_kind {node.pll_kind!r}")


def expand_div_patches(
    index: RegModelIndex,
    node: DivNode,
    settings: SettingsView,
) -> List[_FieldPatch]:
    patches = _rst_pulse_patches(
        index,
        node,
        high_means_reset=settings.div_reg_high_means_reset,
    )
    patches.append(
        _patch(
            index,
            node_name=node.name,
            raw_path=node.regs["div"],
            value=node.cfg["div"],
            note=f"{node.name} div={node.cfg['div']}",
        )
    )
    patches.extend(_load_pulse_patches(index, node))
    return patches


def expand_dto_patches(
    index: RegModelIndex,
    node: DtoNode,
    settings: SettingsView,
) -> List[_FieldPatch]:
    patches = _rst_pulse_patches(
        index,
        node,
        high_means_reset=settings.dto_reg_high_means_reset,
    )
    dto_note = (
        f"{node.name} load={node.cfg['load']} bypass={node.cfg['bypass']} "
        f"step={node.cfg['step']}"
    )
    for key in ("load", "bypass", "step"):
        patches.append(
            _patch(
                index,
                node_name=node.name,
                raw_path=node.regs[key],
                value=node.cfg[key],
                note=dto_note if key == "load" else "",
            )
        )
    return patches


def expand_gate_patch(
    index: RegModelIndex,
    node: GateNode,
    settings: SettingsView,
) -> _FieldPatch:
    if settings.gate_reg_high_means_open:
        value = 1 if node.open else 0
    else:
        value = 0 if node.open else 1
    state = "open" if node.open else "close"
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.reg,
        value=value,
        note=f"{node.name} gate {state}",
    )


def expand_mux_patch(index: RegModelIndex, node: MuxNode) -> _FieldPatch:
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.reg,
        value=node.sel,
        note=f"{node.name} mux sel={node.sel}",
    )


def wait_lock_step(
    index: RegModelIndex,
    node: PllNode,
    settings: SettingsView,
) -> WaitLockStep:
    if "lock" not in node.regs:
        raise ValueError(f"pll 节点 {node.name!r} 的 regs 须含 lock 以轮询")
    ref = index.resolve(node.regs["lock"], ctx=f"节点 {node.name!r} lock")
    return WaitLockStep(
        kind="wait_lock",
        node_name=node.name,
        reg=ref.reg,
        lock_mask=ref.effective_mask,
        timeout_us=settings.lock_timeout_us,
        comment=f"{node.name} wait lock",
    )


def build_config_plan(
    tree: Tree,
    index: RegModelIndex,
    settings: SettingsView,
) -> List[ConfigStep]:
    """按 config_reg 五段顺序生成整 reg 写入与 lock 轮询步骤。"""
    steps: List[ConfigStep] = []
    pll_nodes: List[PllNode] = []
    pll_patches: List[_FieldPatch] = []

    for node in tree.nodes_ordered:
        if isinstance(node, PllNode):
            pll_nodes.append(node)
            pll_patches.extend(expand_pll_patches(index, node))
    steps.extend(merge_field_patches(pll_patches))

    for pll in pll_nodes:
        if pll.pll_kind == "inno" and pll.output_count > 1:
            continue
        steps.append(wait_lock_step(index, pll, settings))

    for node in tree.nodes_ordered:
        if isinstance(node, DivNode):
            steps.extend(merge_field_patches(expand_div_patches(index, node, settings)))
        elif isinstance(node, DtoNode):
            steps.extend(merge_field_patches(expand_dto_patches(index, node, settings)))

    gate_open_patches: List[_FieldPatch] = []
    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and node.open:
            gate_open_patches.append(expand_gate_patch(index, node, settings))
    steps.extend(merge_field_patches(gate_open_patches))

    mux_patches: List[_FieldPatch] = []
    for node in tree.nodes_ordered:
        if isinstance(node, MuxNode):
            mux_patches.append(expand_mux_patch(index, node))
    steps.extend(merge_field_patches(mux_patches))

    gate_close_patches: List[_FieldPatch] = []
    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and not node.open:
            gate_close_patches.append(expand_gate_patch(index, node, settings))
    steps.extend(merge_field_patches(gate_close_patches))

    return _assign_write_step_indices(steps)


def _assign_write_step_indices(steps: List[ConfigStep]) -> List[ConfigStep]:
    out: List[ConfigStep] = []
    write_idx = 0
    for step in steps:
        if isinstance(step, RegWriteStep):
            out.append(
                RegWriteStep(
                    kind=step.kind,
                    node_name=step.node_name,
                    reg=step.reg,
                    value=step.value,
                    comment=step.comment,
                    parts=step.parts,
                    step_index=write_idx,
                )
            )
            write_idx += 1
        else:
            out.append(step)
    return out

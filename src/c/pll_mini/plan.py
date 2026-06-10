from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

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


@dataclass(frozen=True)
class PllRegWrite:
    node_name: str
    addr_macro: str
    value_hex: str
    comment: str


@dataclass(frozen=True)
class PllWaitLock:
    node_name: str
    addr_macro: str
    lock_mask_hex: str
    timeout_us: int
    comment: str


@dataclass(frozen=True)
class DivDevStep:
    node_name: str
    addr_macro: str
    word_rst_assert_hex: str
    word_program_hex: str
    word_load_assert_hex: str
    comment: str

    @property
    def dev_kind(self) -> Literal["div"]:
        return "div"


@dataclass(frozen=True)
class DtoDevStep:
    node_name: str
    writes: tuple[tuple[str, str], ...]
    comment: str

    @property
    def dev_kind(self) -> Literal["dto"]:
        return "dto"


@dataclass(frozen=True)
class GateDevStep:
    node_name: str
    addr_macro: str
    value_hex: str
    comment: str

    @property
    def dev_kind(self) -> Literal["gate"]:
        return "gate"


@dataclass(frozen=True)
class MuxDevStep:
    node_name: str
    addr_macro: str
    value_hex: str
    comment: str

    @property
    def dev_kind(self) -> Literal["mux"]:
        return "mux"


DevStep = DivDevStep | DtoDevStep | GateDevStep | MuxDevStep


@dataclass(frozen=True)
class ConfigPlan:
    pll_writes: tuple[PllRegWrite, ...]
    pll_wait_locks: tuple[PllWaitLock, ...]
    dev_steps: tuple[DevStep, ...]


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
    raise ValueError(f"未知 pll_kind {node.pll_kind!r}")


def expand_div_patches(
    index: RegModelIndex,
    node: DivNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    from formulas import div_ratio_to_n

    patches = _rst_pulse_patches(
        index,
        node,
        high_means_reset=settings.div_reg_high_means_reset,
    )
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
    patches.extend(_load_pulse_patches(index, node))
    return patches


def expand_dto_patches(
    index: RegModelIndex,
    node: DtoNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    step = dto_ratio_to_step(resolved.ratio)
    patches = _rst_pulse_patches(
        index,
        node,
        high_means_reset=settings.dto_reg_high_means_reset,
    )
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


def _reg_writes_to_pll_views(
    writes: List[RegWriteStep],
) -> tuple[PllRegWrite, ...]:
    return tuple(
        PllRegWrite(
            node_name=w.node_name,
            addr_macro=w.addr_macro,
            value_hex=w.value_hex,
            comment=w.comment,
        )
        for w in writes
    )


def _div_dev_step(writes: List[RegWriteStep], node_name: str) -> DivDevStep:
    if len(writes) != 3:
        raise ValueError(
            f"div 节点 {node_name!r} 须产生 3 次寄存器写，得到 {len(writes)}"
        )
    addr = writes[0].addr_macro
    for w in writes[1:]:
        if w.addr_macro != addr:
            raise ValueError(
                f"div 节点 {node_name!r} 的 rst/load/div 须映射到同一寄存器地址"
            )
    return DivDevStep(
        node_name=node_name,
        addr_macro=addr,
        word_rst_assert_hex=writes[0].value_hex,
        word_program_hex=writes[1].value_hex,
        word_load_assert_hex=writes[2].value_hex,
        comment=writes[-1].comment,
    )


def _dto_dev_step(writes: List[RegWriteStep], node_name: str) -> DtoDevStep:
    pairs = tuple((w.addr_macro, w.value_hex) for w in writes)
    return DtoDevStep(
        node_name=node_name,
        writes=pairs,
        comment=writes[-1].comment if writes else node_name,
    )


def _gate_dev_step(write: RegWriteStep) -> GateDevStep:
    return GateDevStep(
        node_name=write.node_name,
        addr_macro=write.addr_macro,
        value_hex=write.value_hex,
        comment=write.comment,
    )


def _mux_dev_step(write: RegWriteStep) -> MuxDevStep:
    return MuxDevStep(
        node_name=write.node_name,
        addr_macro=write.addr_macro,
        value_hex=write.value_hex,
        comment=write.comment,
    )


def build_config_plan(
    tree: Tree,
    index: RegModelIndex,
    settings: SettingsView,
    resolved: TreeResolve,
) -> ConfigPlan:
    """按 config_reg 五段顺序生成 PLL 固化写与器件步骤表。"""
    pll_writes: List[PllRegWrite] = []
    pll_wait_locks: List[PllWaitLock] = []
    dev_steps: List[DevStep] = []
    pll_patches: List[_FieldPatch] = []

    for node in tree.nodes_ordered:
        if not isinstance(node, PllNode) or not node.regs:
            continue
        state = resolved.by_name[node.name]
        if not state.active:
            continue
        pll_patches.extend(expand_pll_patches(index, node, state))
    pll_writes.extend(
        _reg_writes_to_pll_views(merge_field_patches(pll_patches))
    )

    for node in tree.nodes_ordered:
        if not isinstance(node, PllNode) or not node.regs:
            continue
        state = resolved.by_name[node.name]
        if not state.active:
            continue
        if node.pll_kind == "inno" and node.output_count > 1:
            continue
        lock = wait_lock_step(index, node, settings)
        pll_wait_locks.append(
            PllWaitLock(
                node_name=lock.node_name,
                addr_macro=lock.addr_macro,
                lock_mask_hex=lock.lock_mask_hex,
                timeout_us=lock.timeout_us,
                comment=lock.comment,
            )
        )

    for node in tree.nodes_ordered:
        state = resolved.by_name[node.name]
        if not state.active:
            continue
        if isinstance(node, DivNode) and node.regs:
            writes = merge_field_patches(
                expand_div_patches(index, node, settings, state)
            )
            dev_steps.append(_div_dev_step(writes, node.name))
        elif isinstance(node, DtoNode) and node.regs:
            writes = merge_field_patches(
                expand_dto_patches(index, node, settings, state)
            )
            dev_steps.append(_dto_dev_step(writes, node.name))

    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and node.reg:
            state = resolved.by_name[node.name]
            if state.gate_open:
                writes = merge_field_patches(
                    [expand_gate_patch(index, node, settings, state)]
                )
                dev_steps.append(_gate_dev_step(writes[0]))

    for node in tree.nodes_ordered:
        if isinstance(node, MuxNode) and node.reg:
            state = resolved.by_name[node.name]
            if state.active:
                writes = merge_field_patches(
                    [expand_mux_patch(index, node, state)]
                )
                dev_steps.append(_mux_dev_step(writes[0]))

    for node in tree.nodes_ordered:
        if isinstance(node, GateNode) and node.reg:
            state = resolved.by_name[node.name]
            if not state.gate_open:
                writes = merge_field_patches(
                    [expand_gate_patch(index, node, settings, state)]
                )
                dev_steps.append(_gate_dev_step(writes[0]))

    return ConfigPlan(
        pll_writes=tuple(pll_writes),
        pll_wait_locks=tuple(pll_wait_locks),
        dev_steps=tuple(dev_steps),
    )

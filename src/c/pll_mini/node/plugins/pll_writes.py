from __future__ import annotations

from typing import List

from load.regmodel import RegModelIndex
from registers.plan import _FieldPatch, _patch
from registers.resolve import ResolvedNode

from node.plugins.pll import PllNode

from .config_paths import inno_postdiv_reg_keys


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
    ctrl_note = f"{node.name} bypass=1 pwrdn=0 reset=1"
    for key, val in zip(PLL_TCI_CTRL_KEYS, (1, 0, 1), strict=True):
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
    shared = f"{node.name} refdiv={cfg['refdiv']} fbdiv={cfg['fbdiv']}"
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
    for group_id in node.output_groups:
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        post = (
            f"{node.name} out[{group_id}] postdiv1={cfg[p1_key]} postdiv2={cfg[p2_key]}"
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


def _pll_lock_view(
    index: RegModelIndex,
    node: PllNode,
) -> tuple[str, str]:
    if "lock" not in node.regs:
        raise ValueError(f"pll node {node.name!r} requires regs.lock")
    ref = index.resolve(node.regs["lock"], ctx=f"node {node.name!r} lock")
    mask_hex = f"0x{(ref.effective_mask & 0xFFFFFFFF):X}"
    return ref.reg.addr_macro, mask_hex


def _pll_fn_name(node_name: str) -> str:
    return f"pll_mini_config_{node_name}"


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

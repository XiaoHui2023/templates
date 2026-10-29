from __future__ import annotations

from typing import List

from load.regmodel import RegModelIndex
from registers.plan import SettingsView, _FieldPatch, _patch
from registers.resolve import ResolvedNode

from node.plugins.div import DivNode
from node.plugins.divider_math import dto_ratio_to_step


def _reset_release_patch(
    index: RegModelIndex,
    node: DivNode,
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


def expand_div_patches(
    index: RegModelIndex,
    node: DivNode,
    settings: SettingsView,
    resolved: ResolvedNode,
) -> List[_FieldPatch]:
    if node.div_kind in ("dto", "dto_n"):
        return expand_dto_patches(index, node, settings, resolved)

    from node.plugins.divider_math import div_ratio_to_n

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
    node: DivNode,
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
    dto_note = f"{node.name} ratio={resolved.ratio} load=1 bypass=0 step={step}"
    for key, val in zip(("load", "bypass", "step"), (1, 0, step), strict=True):
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

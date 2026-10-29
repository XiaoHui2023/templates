from __future__ import annotations

from load.regmodel import RegModelIndex
from registers.plan import SettingsView, _FieldPatch, _patch

from node.plugins.gate import GateNode


def expand_gate_patch(
    index: RegModelIndex,
    node: GateNode,
    settings: SettingsView,
) -> _FieldPatch:
    value = 1 if settings.gate_reg_high_means_open else 0
    return _patch(
        index,
        node_name=node.name,
        raw_path=node.reg,
        value=value,
        note=f"{node.name} gate open",
    )

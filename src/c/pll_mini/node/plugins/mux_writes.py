from __future__ import annotations

from load.regmodel import RegModelIndex
from registers.plan import _FieldPatch, _patch
from registers.resolve import ResolvedNode

from node.plugins.mux import MuxNode


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

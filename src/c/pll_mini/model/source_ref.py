from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Protocol

from reg_paths import node_output_groups

_SOURCE_ENDPOINT = re.compile(
    r"^(?P<device>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<group>[^\]]+)\])?$"
)
_GROUP_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


class _PeerNode(Protocol):
    kind: str

    @property
    def div_kind(self) -> str: ...

    @property
    def pll_kind(self) -> str: ...


def normalize_source_endpoint_input(raw: Any, *, ctx: str) -> str:
    if isinstance(raw, str):
        return raw.strip()
    raise ValueError(f"{ctx} 前级引用 {raw!r} 应为字符串")


def parse_source_endpoint(raw: Any, *, ctx: str) -> tuple[str, str]:
    """解析前级引用语法：器件名，或多路输出时的 器件名[输出名]。"""
    text = normalize_source_endpoint_input(raw, ctx=ctx)
    match = _SOURCE_ENDPOINT.match(text)
    if not match:
        raise ValueError(
            f"{ctx} 前级引用 {raw!r} 应为器件名或 器件名[输出名] 形式"
        )
    device = match.group("device")
    group_text = match.group("group")
    out_group = group_text if group_text is not None else ""
    if out_group and not _GROUP_KEY_RE.match(out_group):
        raise ValueError(
            f"{ctx} 前级引用 {raw!r} 中输出名 {out_group!r} "
            f"应为合法 SystemVerilog 名字"
        )
    return device, out_group


def _peer_kind_label(peer: _PeerNode) -> str:
    kind = peer.kind
    if kind == "div":
        return f"div({peer.div_kind})"
    if kind == "pll":
        return f"pll({peer.pll_kind})"
    return kind


def _format_allowed_outputs(groups: list[str]) -> str:
    return "、".join(groups)


def _output_name_confusion_hint(
    out_group: str,
    *,
    device: str,
    nodes: Mapping[str, _PeerNode],
) -> str:
    if out_group not in nodes or out_group == device:
        return ""
    other = nodes[out_group]
    if other.kind == "clk":
        return (
            f"；nodes 中有 clk 节点 {out_group!r}，"
            f"不能当作 {device!r} 的输出名或前级"
        )
    return (
        f"；nodes 中有节点 {out_group!r}（{other.kind}），"
        f"这不是 {device!r} 的输出名"
    )


def validate_source_ref(
    raw: str,
    nodes: Dict[str, _PeerNode],
    *,
    ctx: str,
) -> None:
    """校验前级引用的器件存在、可作前级，且输出名与器件多路输出规则一致。"""
    device, out_group = parse_source_endpoint(raw, ctx=ctx)
    if device not in nodes:
        raise ValueError(f"{ctx} 引用器件 {device!r} 不在 nodes 中")
    peer = nodes[device]
    label = _peer_kind_label(peer)

    if peer.kind == "clk":
        raise ValueError(
            f"{ctx} 引用 {raw!r}：节点 {device!r} 为 clk，"
            f"只做频率终点、无输出，不可作为其它节点的前级"
        )

    groups = node_output_groups(peer)
    if not groups:
        if out_group:
            raise ValueError(
                f"{ctx} 引用 {raw!r}：{device!r} 为 {label}，"
                f"仅单路输出、无命名输出端口，应写 {device!r} "
                f"而非 {device}[{out_group}]"
            )
        return

    allowed = _format_allowed_outputs(groups)
    if not out_group:
        example = f"{device}[{groups[0]}]"
        raise ValueError(
            f"{ctx} 引用 {raw!r}：{device!r} 为 {label}，"
            f"有多路输出，应写 {example} 等形式；允许的名字为 {allowed}"
        )
    if out_group not in groups:
        hint = _output_name_confusion_hint(out_group, device=device, nodes=nodes)
        raise ValueError(
            f"{ctx} 引用 {raw!r}：输出名 {out_group!r} 不是 {device!r} "
            f"的有效输出；允许的名字为 {allowed}{hint}"
        )


def validate_nodes_source_refs(
    nodes: Mapping[str, Any],
) -> None:
    """遍历各节点 source / mux.source，校验全部前级引用。"""
    node_map = dict(nodes)
    for key, node in nodes.items():
        name = getattr(node, "name", key)
        if name != key:
            raise ValueError(
                f"nodes[{key!r}] 的 name 字段 {name!r} 应与字典键一致"
            )
        if node.kind == "mux":
            for mux_key, peer in node.source.items():
                validate_source_ref(
                    peer,
                    node_map,
                    ctx=f"节点 {name!r} mux.source[{mux_key!r}]",
                )
        elif node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
            if node.source.strip():
                validate_source_ref(
                    node.source,
                    node_map,
                    ctx=f"节点 {name!r} source",
                )

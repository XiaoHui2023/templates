from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .source_ref import parse_source_endpoint

if TYPE_CHECKING:
    from .nodes import Tree


@dataclass(frozen=True, order=True)
class Port:
    """节点输出端口，单输出使用空 group。"""

    node: str
    group: str = ""


def output_ports(tree: Tree, node_name: str) -> list[Port]:
    """展开插件声明的输出端口。"""
    return [
        Port(node_name, group) for group in tree.nodes[node_name].output_groups or [""]
    ]


def parse_port_ref(raw: str, *, ctx: str) -> Port:
    """解析一个上游端口引用。"""
    return Port(*parse_source_endpoint(raw, ctx=ctx))


def node_has_upstream_ref(node) -> bool:
    """判断节点是否有上游输入。"""
    return bool(node.input_refs())


def parent_port_for_child(tree: Tree, child_name: str) -> Port:
    """返回单输入节点的上游端口。

    Raises:
        ValueError: 节点没有默认单输入。
    """
    raw = tree.nodes[child_name].input_refs().get("")
    if not raw:
        raise ValueError(f"nodes[{child_name!r}].source 无默认单输入")
    return parse_port_ref(raw, ctx=f"nodes[{child_name!r}].source")


def collect_freq_targets(tree: Tree) -> list[tuple[str, int]]:
    """收集插件声明的正频率目标。"""
    return [
        (name, node.fixed_hz() or 0)
        for name, node in tree.nodes.items()
        if node.is_target and (node.fixed_hz() or 0) > 0
    ]


def collect_non_frequency_targets(tree: Tree) -> list[str]:
    """收集未指定正频率的目标节点。"""
    return [
        name
        for name, node in tree.nodes.items()
        if node.is_target and (node.fixed_hz() or 0) <= 0 and node.input_refs()
    ]


def walk_path_upstream(
    tree: Tree, start: str, *, stop_at: str | None = None, model=None
) -> list[str]:
    """沿插件选中的输入遍历，遇到无输入时停止。"""
    chain, seen = [], set()
    name = start
    while name not in seen:
        seen.add(name)
        chain.append(name)
        if name == stop_at:
            break
        raw = tree.nodes[name].selected_input(model)
        if not raw:
            break
        name = parse_port_ref(raw, ctx=f"nodes[{name!r}].source").node
    return chain


def path_between_ports(tree: Tree, *, from_port: Port, to_clk: str) -> list[str]:
    """寻找从上游端口到目标的下游路径。"""
    queue = deque([(from_port.node, [from_port.node])])
    seen = set()
    children = tree.children_by_node
    while queue:
        name, path = queue.popleft()
        if name == to_clk:
            return path
        if name in seen:
            continue
        seen.add(name)
        queue.extend((child, [*path, child]) for child in children[name])
    return list(reversed(walk_path_upstream(tree, to_clk)))


def port_label(port: Port, tree: Tree) -> str:
    """返回包含输出名的端口标签。"""
    return port.node + (f"[{port.group}]" if port.group else "")


def static_port_hz(tree: Tree, model, port: Port, seen: set[Port] | None = None) -> int:
    """由插件回放固定路径频率，防止循环递归。"""
    seen = set() if seen is None else seen
    if port in seen:
        return 0
    seen.add(port)
    hz = model.port_hz(port)
    if hz > 0:
        return hz
    node = tree.nodes[port.node]
    return node.static_hz(
        tree,
        model,
        port.group,
        lambda raw: static_port_hz(
            tree, model, parse_port_ref(raw, ctx=port.node), seen
        ),
    )

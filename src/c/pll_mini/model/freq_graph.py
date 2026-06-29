from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from .nodes import (
    ClkNode,
    DivNode,
    GateNode,
    MuxNode,
    PllNode,
    Tree,
    parse_source_endpoint,
)
from reg_paths import (
    CPU_GATE_PASS_THROUGH_GROUP,
    node_output_groups,
)


@dataclass(frozen=True, order=True)
class Port:
    """节点输出端口；单路输出时 group 为空字符串。"""

    node: str
    group: str = ""


def output_ports(tree: Tree, node_name: str) -> List[Port]:
    node = tree.nodes[node_name]
    groups = node_output_groups(node)
    if groups:
        return [Port(node_name, group) for group in groups]
    return [Port(node_name, "")]


def parse_port_ref(raw: str, *, ctx: str) -> Port:
    device, out_group = parse_source_endpoint(raw, ctx=ctx)
    return Port(device, out_group)


def collect_freq_targets(tree: Tree) -> List[Tuple[str, int]]:
    """带正频率约束的 clk 节点。"""
    out: List[Tuple[str, int]] = []
    for name, node in tree.nodes.items():
        if isinstance(node, ClkNode) and node.freq is not None and node.freq > 0:
            out.append((name, node.freq))
    return out


def _upstream_peer_ports(tree: Tree, node_name: str) -> List[Port]:
    node = tree.nodes[node_name]
    if node.kind == "source":
        return []
    if isinstance(node, MuxNode):
        return []
    if node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
        return [parse_port_ref(node.source, ctx=f"{node_name}.source")]
    return []


def _mux_selected_peer(tree: Tree, mux_name: str) -> str | None:
    mux = tree.nodes[mux_name]
    if not isinstance(mux, MuxNode) or mux.sel is None:
        return None
    key = str(mux.sel)
    arm_ref = mux.source.get(key)
    if not arm_ref:
        return None
    peer_name, _ = parse_source_endpoint(arm_ref, ctx=f"mux {mux_name!r}")
    return peer_name


def is_static_frequency_anchor(
    tree: Tree,
    node_name: str,
    *,
    via_port: Port | None = None,
) -> bool:
    """从下游触及该节点时，是否视为固定频率边界并停止继续向上回溯。"""
    if node_name not in tree.nodes:
        return False
    node = tree.nodes[node_name]
    if node.kind == "source":
        return True
    if isinstance(node, PllNode):
        if node.pll_kind == "inno":
            return bool(via_port and via_port.group)
        return node.freq is not None and node.freq > 0
    return False


def is_static_frequency_anchor_node(tree: Tree, node_name: str) -> bool:
    """节点是否属于固定频率边界类型，用于子树合并时排除共享锚点。"""
    if node_name not in tree.nodes:
        return False
    node = tree.nodes[node_name]
    if node.kind == "source":
        return True
    if isinstance(node, PllNode):
        return node.pll_kind == "inno" or (
            node.freq is not None and node.freq > 0
        )
    return False


def is_propagation_boundary_node(tree: Tree, node_name: str) -> bool:
    """频率透传 hub，可作为传播锚点切断上游子树。"""
    if node_name not in tree.nodes:
        return False
    node = tree.nodes[node_name]
    if is_passthrough_kind(node.kind):
        return True
    if isinstance(node, GateNode) and node.open != 0:
        return True
    return False


def is_merge_exempt_for_partition(tree: Tree, node_name: str) -> bool:
    """无寄存器或配置已写死的节点不参与 clk 子树合并判定。"""
    if is_static_frequency_anchor_node(tree, node_name):
        return True
    node = tree.nodes.get(node_name)
    if node is None:
        return True
    if node.kind in ("inv", "cell"):
        return True
    if isinstance(node, GateNode) and node.open in (0, 1):
        return True
    if isinstance(node, MuxNode) and node.sel is not None:
        return True
    if isinstance(node, DivNode) and node.div_kind == "div_r" and node.ratio is not None:
        return True
    return False


def inverse_hz_at_node_from_clk(
    tree: Tree,
    clk_name: str,
    clk_hz: int,
    node_name: str,
) -> int | None:
    """从 clk 目标反推 node 输出 Hz；路径上仅允许透传与 ratio 已写的 div。"""
    path = _downstream_path(tree, node_name, clk_name)
    if path is None:
        return None
    req = clk_hz
    idx = path.index(node_name)
    for downstream in reversed(path[idx + 1 :]):
        node = tree.nodes[downstream]
        if node.kind in ("gate", "inv", "cell", "clk"):
            continue
        if isinstance(node, MuxNode):
            continue
        if isinstance(node, DivNode):
            ratio = node.ratio
            if ratio is None:
                return None
            if node.div_kind == "cpu_gate":
                upstream = resolve_upstream_port(tree, clk_name)
                if (
                    upstream is not None
                    and upstream.node == downstream
                    and is_cpu_gate_passthrough_group(upstream.group)
                ):
                    continue
            if node.div_kind != "cpu_gate" or downstream != node_name:
                req *= ratio
    return req if req > 0 else None


def propagate_determined_ports(
    tree: Tree,
    targets: List[Tuple[str, int]],
) -> Dict[Port, int]:
    """分区前标注可由某 clk 目标反推确定 Hz 的透传 hub 输出端口。"""
    determined: Dict[Port, int] = {}
    conflicts: Set[Port] = set()
    for clk_name, clk_hz in targets:
        for node_name in _transparent_upstream_chain_from_clk(tree, clk_name):
            if not is_propagation_boundary_node(tree, node_name):
                continue
            hz = inverse_hz_at_node_from_clk(tree, clk_name, clk_hz, node_name)
            if hz is None:
                continue
            port = Port(node_name, "")
            if port in conflicts:
                continue
            prev = determined.get(port)
            if prev is not None and prev != hz:
                conflicts.add(port)
                determined.pop(port, None)
            else:
                determined[port] = hz
    return determined


def _transparent_upstream_chain_from_clk(tree: Tree, clk_name: str) -> List[str]:
    chain = [clk_name]
    name = clk_name
    seen = {clk_name}
    while True:
        node = tree.nodes[name]
        if node.kind == "source":
            break
        if isinstance(node, PllNode):
            if node.pll_kind == "inno":
                break
            if node.freq is not None and node.freq > 0:
                break
        if isinstance(node, MuxNode):
            break
        if isinstance(node, DivNode):
            if node.ratio is None and node.div_kind != "div_r":
                break
        if isinstance(node, GateNode) and node.open == 0:
            break
        try:
            parent_port = parent_port_for_child(tree, name)
        except ValueError:
            break
        parent_name = parent_port.node
        if parent_name in seen:
            break
        if is_static_frequency_anchor(tree, parent_name, via_port=parent_port):
            chain.append(parent_name)
            break
        parent = tree.nodes[parent_name]
        if isinstance(parent, MuxNode):
            break
        seen.add(parent_name)
        chain.append(parent_name)
        name = parent_name
    return chain


def _has_sibling_branch_at_hub(
    tree: Tree,
    hub: str,
    clk_det: str,
    clk_cur: str,
) -> bool:
    if clk_det == clk_cur:
        return False
    path_det = _downstream_path(tree, hub, clk_det)
    path_cur = _downstream_path(tree, hub, clk_cur)
    if path_det is None or path_cur is None:
        return False
    if len(path_det) < 2 or len(path_cur) < 2:
        return path_det != path_cur
    return path_det[1] != path_cur[1]


def _transparent_path_between(tree: Tree, hub: str, clk_name: str) -> bool:
    path = _downstream_path(tree, hub, clk_name)
    if path is None or len(path) < 2:
        return False
    for mid in path[1:-1]:
        node = tree.nodes[mid]
        if isinstance(node, ClkNode):
            continue
        if not is_passthrough_kind(node.kind):
            if isinstance(node, GateNode) and node.open != 0:
                continue
            return False
    return True


def should_cut_upstream_at_node(
    tree: Tree,
    node_name: str,
    component_targets: List[Tuple[str, int]],
    all_targets: List[Tuple[str, int]],
    determined_ports: Dict[Port, int],
) -> bool:
    """另一路 clk 已确定 hub 频率时，当前目标子树在 hub 处截断、不再向上游搜索。"""
    if not is_propagation_boundary_node(tree, node_name):
        return False
    port = Port(node_name, "")
    hz_det = determined_ports.get(port)
    if hz_det is None:
        return False
    for clk_name, clk_hz in component_targets:
        inv = inverse_hz_at_node_from_clk(tree, clk_name, clk_hz, node_name)
        if inv == hz_det and _transparent_path_between(tree, node_name, clk_name):
            return False
    component_clks = {name for name, _ in component_targets}
    for clk_name, clk_hz in all_targets:
        if clk_name in component_clks:
            continue
        if _downstream_path(tree, node_name, clk_name) is None:
            continue
        if inverse_hz_at_node_from_clk(tree, clk_name, clk_hz, node_name) != hz_det:
            continue
        for comp_clk, _ in component_targets:
            if _has_sibling_branch_at_hub(tree, node_name, clk_name, comp_clk):
                return True
    return False


def backward_required_nodes_bounded(
    tree: Tree,
    targets: List[Tuple[str, int]],
    *,
    all_targets: List[Tuple[str, int]] | None = None,
    determined_ports: Dict[Port, int] | None = None,
) -> Set[str]:
    """从 clk 目标反向收集节点，在 source / 固定 freq 的 pll / inno 输出端口处截断。"""
    required, _anchors = backward_required_nodes_for_partition(
        tree,
        targets,
        all_targets=all_targets or targets,
        determined_ports=determined_ports or {},
    )
    return required


def backward_required_nodes_for_partition(
    tree: Tree,
    component_targets: List[Tuple[str, int]],
    *,
    all_targets: List[Tuple[str, int]],
    determined_ports: Dict[Port, int],
) -> Tuple[Set[str], Dict[Port, int]]:
    """反向收集参与求解的节点；在传播锚点 hub 处截断并返回注入频率。"""
    required: Set[str] = set()
    port_anchors: Dict[Port, int] = {}
    stack: List[str] = [name for name, _hz in component_targets]
    while stack:
        name = stack.pop()
        if name in required:
            continue
        if name not in tree.nodes:
            continue
        required.add(name)
        node = tree.nodes[name]
        if node.kind == "source":
            continue
        if isinstance(node, PllNode):
            if node.pll_kind == "inno":
                continue
            if node.freq is not None and node.freq > 0:
                continue
        if should_cut_upstream_at_node(
            tree,
            name,
            component_targets,
            all_targets,
            determined_ports,
        ):
            port = Port(name, "")
            hz = determined_ports.get(port)
            if hz is not None:
                port_anchors[port] = hz
            continue
        if isinstance(node, MuxNode):
            if node.sel is not None:
                peer = _mux_selected_peer(tree, name)
                if peer is not None:
                    stack.append(peer)
            else:
                for arm_ref in node.source.values():
                    peer_name, _ = parse_source_endpoint(
                        arm_ref, ctx=f"mux {name!r}"
                    )
                    stack.append(peer_name)
            continue
        for port in _upstream_peer_ports(tree, name):
            parent_name = port.node
            if is_static_frequency_anchor(tree, parent_name, via_port=port):
                required.add(parent_name)
                continue
            parent = tree.nodes[parent_name]
            if isinstance(parent, MuxNode):
                stack.append(parent_name)
                peer = _mux_selected_peer(tree, parent_name)
                if peer is not None:
                    stack.append(peer)
            else:
                stack.append(parent_name)
    return required, port_anchors


def backward_required_nodes_pll_ref(tree: Tree, pll_name: str) -> Set[str]:
    """从 PLL 参考输入端向上收集节点，仅止于 source。"""
    if pll_name not in tree.nodes:
        return set()
    pll = tree.nodes[pll_name]
    if not isinstance(pll, PllNode):
        return set()
    required: Set[str] = {pll_name}
    ref_name, _ = parse_source_endpoint(pll.source, ctx=f"{pll_name}.source")
    stack: List[str] = [ref_name]
    while stack:
        name = stack.pop()
        if name in required:
            continue
        if name not in tree.nodes:
            continue
        required.add(name)
        node = tree.nodes[name]
        if node.kind == "source":
            continue
        if isinstance(node, PllNode):
            up_name, _ = parse_source_endpoint(node.source, ctx=f"{pll_name}.ref")
            stack.append(up_name)
            continue
        if isinstance(node, MuxNode):
            if node.sel is not None:
                peer = _mux_selected_peer(tree, name)
                if peer is not None:
                    stack.append(peer)
            else:
                for arm_ref in node.source.values():
                    peer_name, _ = parse_source_endpoint(
                        arm_ref, ctx=f"mux {name!r}"
                    )
                    stack.append(peer_name)
            continue
        for port in _upstream_peer_ports(tree, name):
            stack.append(port.node)
    return required


def backward_required_nodes(
    tree: Tree,
    targets: List[Tuple[str, int]],
) -> Set[str]:
    """从频率目标 clk 反向标记须参与求解的节点。"""
    required: Set[str] = set()
    stack: List[str] = [name for name, _hz in targets]
    while stack:
        name = stack.pop()
        if name in required:
            continue
        if name not in tree.nodes:
            continue
        required.add(name)
        node = tree.nodes[name]
        if node.kind == "source":
            continue
        if isinstance(node, MuxNode):
            if node.sel is not None:
                peer = _mux_selected_peer(tree, name)
                if peer is not None:
                    stack.append(peer)
            else:
                for arm_ref in node.source.values():
                    peer_name, _ = parse_source_endpoint(
                        arm_ref, ctx=f"mux {name!r}"
                    )
                    stack.append(peer_name)
            continue
        for port in _upstream_peer_ports(tree, name):
            parent = tree.nodes[port.node]
            if isinstance(parent, MuxNode):
                stack.append(port.node)
                peer = _mux_selected_peer(tree, port.node)
                if peer is not None:
                    stack.append(peer)
            else:
                stack.append(port.node)
    return required


def child_input_port(child_name: str) -> Port:
    """子节点消费的前级输出端口在子节点侧的输入频率符号与父端口相同。"""
    return Port(child_name, "__in")


def parent_port_for_child(tree: Tree, child_name: str) -> Port:
    node = tree.nodes[child_name]
    if node.kind == "source":
        raise ValueError(f"source 节点 {child_name!r} 无前级")
    if isinstance(node, MuxNode):
        raise ValueError(f"mux 节点 {child_name!r} 用 mux 专用约束")
    if node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
        return parse_port_ref(node.source, ctx=f"{child_name}.source")
    raise ValueError(f"节点 {child_name!r} 无前级引用")


def passthrough_kinds() -> frozenset[str]:
    return frozenset({"gate", "inv", "cell"})


def is_passthrough_kind(kind: str) -> bool:
    return kind in passthrough_kinds()


def is_frequency_transparent_kind(kind: str) -> bool:
    """频率约束上 f_out = f_in 的节点；含 gate、inv、cell。"""
    return is_passthrough_kind(kind) or kind == "gate"


def resolve_upstream_port(tree: Tree, start: str) -> Port | None:
    """从 start 沿频率透明链向上，解析实际驱动它的前级输出端口。"""
    cur = start
    seen: Set[str] = set()
    while cur not in seen:
        seen.add(cur)
        node = tree.nodes.get(cur)
        if node is None:
            return None
        if node.kind == "source":
            return Port(cur, "")
        if isinstance(node, MuxNode):
            return Port(cur, "")
        if isinstance(node, ClkNode):
            source_ref = node.source
        elif is_frequency_transparent_kind(node.kind):
            source_ref = node.source
        elif isinstance(node, (DivNode, PllNode)):
            source_ref = node.source
        else:
            return None
        parent_name, parent_group = parse_source_endpoint(
            source_ref, ctx=f"{node.kind} {cur!r}"
        )
        parent = tree.nodes.get(parent_name)
        if parent is None:
            return None
        if isinstance(parent, (DivNode, PllNode)) or parent.kind == "source":
            return Port(parent_name, parent_group)
        if isinstance(parent, MuxNode):
            return Port(parent_name, "")
        if is_frequency_transparent_kind(parent.kind):
            cur = parent_name
            continue
        return None
    return None


def clk_driven_by_port(tree: Tree, clk_name: str, port: Port) -> bool:
    """clk 经频率透明链是否由指定端口驱动。"""
    resolved = resolve_upstream_port(tree, clk_name)
    return resolved == port


def walk_path_upstream(
    tree: Tree,
    start: str,
    *,
    stop_at: str | None = None,
) -> List[str]:
    """从 start 沿 source 向上走到 source 或 stop_at。"""
    chain = [start]
    name = start
    seen = {start}
    while True:
        if stop_at is not None and name == stop_at:
            break
        node = tree.nodes[name]
        if node.kind == "source":
            break
        if isinstance(node, MuxNode):
            peer = _mux_selected_peer(tree, name)
            if peer is None or peer in seen:
                break
            seen.add(peer)
            chain.append(peer)
            name = peer
            continue
        parent_port = parent_port_for_child(tree, name)
        parent_name = parent_port.node
        if parent_name in seen:
            break
        parent = tree.nodes[parent_name]
        if isinstance(parent, MuxNode):
            seen.add(parent_name)
            chain.append(parent_name)
            peer = _mux_selected_peer(tree, parent_name)
            if peer is None or peer in seen:
                break
            seen.add(peer)
            chain.append(peer)
            name = peer
            continue
        seen.add(parent_name)
        chain.append(parent_name)
        name = parent_name
    return chain


def path_between_ports(
    tree: Tree,
    *,
    from_port: Port,
    to_clk: str,
) -> List[str]:
    """从父端口所在节点到目标 clk 的下游路径节点名列表。"""
    down = _downstream_path(tree, from_port.node, to_clk)
    if down is None:
        return walk_path_upstream(tree, to_clk)
    up = list(reversed(walk_path_upstream(tree, to_clk, stop_at=from_port.node)))
    if from_port.node in up:
        idx = up.index(from_port.node)
        return up[idx:] + down[1:]
    return up + down


def _downstream_path(tree: Tree, start: str, target: str) -> List[str] | None:
    if start == target:
        return [start]
    parent_of: Dict[str, str] = {}
    queue = [start]
    seen = {start}
    while queue:
        name = queue.pop(0)
        for child in _downstream_children(tree, name):
            if child in seen:
                continue
            seen.add(child)
            parent_of[child] = name
            if child == target:
                path = [target]
                cur = name
                while True:
                    path.append(cur)
                    if cur == start:
                        break
                    cur = parent_of[cur]
                path.reverse()
                return path
            queue.append(child)
    return None


def _downstream_children(tree: Tree, name: str) -> List[str]:
    children: List[str] = []
    for other_name, other in tree.nodes.items():
        if other_name == name:
            continue
        if isinstance(other, MuxNode):
            for arm_ref in other.source.values():
                arm_name, _ = parse_source_endpoint(
                    arm_ref, ctx=f"downstream mux {other_name!r}"
                )
                if arm_name == name:
                    children.append(other_name)
            continue
        if other.kind == "source":
            continue
        try:
            parent_port = parent_port_for_child(tree, other_name)
        except ValueError:
            continue
        if parent_port.node == name:
            children.append(other_name)
    return children


def port_label(port: Port, tree: Tree) -> str:
    node = tree.nodes[port.node]
    kind = getattr(node, "kind", "?")
    if port.group:
        return f"{port.node}[{port.group}] ({kind})"
    return f"{port.node} ({kind})"


def is_cpu_gate_passthrough_group(group: str) -> bool:
    return group == CPU_GATE_PASS_THROUGH_GROUP


def reaches_clk_without_mux(
    tree: Tree,
    start: str,
    *,
    skip_mux: str,
) -> bool:
    targets = {name for name, _ in collect_freq_targets(tree)}
    seen: set[str] = set()
    stack = [start]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in targets:
            return True
        for child in _downstream_children(tree, name):
            if child == skip_mux:
                continue
            stack.append(child)
    return False


def is_mux_exclusive_peer(tree: Tree, mux_name: str, peer_name: str) -> bool:
    return not reaches_clk_without_mux(tree, peer_name, skip_mux=mux_name)

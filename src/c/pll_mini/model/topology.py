from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .nodes import MuxNode, Tree, parse_source_endpoint
from .freq_graph import parent_port_for_child


@dataclass
class TreeTopology:
    """时钟树下游邻接与路径查询缓存，避免搜索内重复 BFS。"""

    children: Dict[str, tuple[str, ...]]
    _path_cache: Dict[Tuple[str, str], tuple[str, ...] | None] = field(
        default_factory=dict,
        repr=False,
    )

    @classmethod
    def build(cls, tree: Tree) -> TreeTopology:
        children: Dict[str, tuple[str, ...]] = {}
        for name in tree.nodes:
            kids: List[str] = []
            for other_name, other in tree.nodes.items():
                if other_name == name or other.kind == "source":
                    continue
                if isinstance(other, MuxNode):
                    for arm in other.source.values():
                        arm_name, _ = parse_source_endpoint(arm, ctx="child")
                        if arm_name == name:
                            kids.append(other_name)
                    continue
                try:
                    parent = parent_port_for_child(tree, other_name)
                except ValueError:
                    continue
                if parent.node == name:
                    kids.append(other_name)
            children[name] = tuple(sorted(kids))
        return cls(children=children)

    def downstream_children(self, name: str) -> tuple[str, ...]:
        return self.children.get(name, ())

    def find_downstream_path(self, start: str, target: str) -> tuple[str, ...] | None:
        key = (start, target)
        if key in self._path_cache:
            return self._path_cache[key]
        path = self._compute_path(start, target)
        self._path_cache[key] = path
        return path

    def _compute_path(self, start: str, target: str) -> tuple[str, ...] | None:
        if start == target:
            return (start,)
        parent_of: Dict[str, str] = {}
        queue = [start]
        seen = {start}
        while queue:
            name = queue.pop(0)
            for child in self.downstream_children(name):
                if child in seen:
                    continue
                seen.add(child)
                parent_of[child] = name
                if child == target:
                    path: List[str] = [target]
                    cur = name
                    while True:
                        path.append(cur)
                        if cur == start:
                            break
                        cur = parent_of[cur]
                    path.reverse()
                    return tuple(path)
                queue.append(child)
        return None


_active_topology: TreeTopology | None = None


def bind_tree_topology(tree: Tree) -> TreeTopology:
    global _active_topology
    _active_topology = TreeTopology.build(tree)
    return _active_topology


def active_tree_topology() -> TreeTopology | None:
    return _active_topology


def clear_tree_topology() -> None:
    global _active_topology
    _active_topology = None

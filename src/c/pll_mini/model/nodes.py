from __future__ import annotations

import re
from typing import Any, Dict, List
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    computed_field,
    field_validator,
    model_validator,
)
from node.base import NodeBase
from node.registry import normalize_node_item, parse_node
from model.source_ref import parse_source_endpoint, validate_nodes_source_refs
from reg_paths import validate_reg_path

Node = SerializeAsAny[NodeBase]
_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def node_has_upstream_ref(node: NodeBase) -> bool:
    return bool(node.input_refs())


def upstream_peer_names(node: NodeBase) -> List[str]:
    return list(
        dict.fromkeys(
            parse_source_endpoint(raw, ctx=f"nodes[{node.name!r}].source")[0]
            for raw in node.input_refs().values()
        )
    )


def _is_omitted_node(value: Any) -> bool:
    return value is None or (isinstance(value, dict) and value.get("exclude") is True)


class ExtraRegEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        min_length=1,
        description="寄存器模型路径，按 `.` 分隔，可带比特范围。",
    )
    value: int = Field(..., description="写入该 field 的整数值。")

    @field_validator("path")
    @classmethod
    def _validate_path_syntax(cls, value: str) -> str:
        validate_reg_path(value, ctx="extra_regs.path")
        return value


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键即节点名；节点体内勿填 name。",
    )
    extra_regs: List[ExtraRegEntry] = Field(
        default_factory=list,
        description="PLL 锁定等待之后、普通器件 steps 之前写入的寄存器 field 列表。",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_nodes_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        nodes = data.get("nodes")
        if nodes is None:
            return data
        if isinstance(nodes, list):
            as_dict: dict[str, Any] = {}
            for item in nodes:
                if _is_omitted_node(item):
                    continue
                if not isinstance(item, dict):
                    as_dict[str(item)] = item
                    continue
                item = normalize_node_item(item)
                node_name = item.get("name")
                if not node_name:
                    raise ValueError(
                        "nodes 为列表时每项须含 name；请改用 dict，以键为 name"
                    )
                body = {k: v for k, v in item.items() if k != "name"}
                as_dict[str(node_name)] = body
            nodes = as_dict
        if not isinstance(nodes, dict):
            return data
        normalized: dict[str, Any] = {}
        for key, item in nodes.items():
            if not _SV_ID.match(key):
                raise ValueError(f"nodes 键 {key!r} 须为合法 SystemVerilog 名字")
            if _is_omitted_node(item):
                continue
            if isinstance(item, dict):
                item = normalize_node_item(item)
                if "name" in item:
                    raise ValueError(
                        f"nodes[{key!r}] 体内不可含 name，以字典键 {key!r} 为准"
                    )
                normalized[key] = item
            else:
                normalized[key] = item
        return {**data, "nodes": normalized}

    @field_validator("nodes", mode="before")
    @classmethod
    def _build_nodes_from_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        built: Dict[str, Node] = {}
        for key, item in value.items():
            if _is_omitted_node(item):
                continue
            if isinstance(item, NodeBase):
                object.__setattr__(item, "_name", key)
                built[key] = item
                continue
            node = parse_node(key, item)
            object.__setattr__(node, "_name", key)
            built[key] = node
        return built

    @computed_field(  # type: ignore[prop-decorator]
        description="nodes 值的有序列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def nodes_ordered(self) -> List[Node]:
        return list(self.nodes.values())

    @computed_field(  # type: ignore[prop-decorator]
        description="由各节点 source 反查；键为器件名，值为以其为前级的子节点名列表。",
    )
    @property
    def children_by_node(self) -> Dict[str, List[str]]:
        return build_children_map(self.nodes)

    @model_validator(mode="after")
    def _validate_nodes_graph(self) -> Tree:
        validate_nodes_graph(self.nodes)
        return self


def build_children_map(nodes: Dict[str, Node]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {key: [] for key in nodes}
    for child_name, node in nodes.items():
        for parent_name in upstream_peer_names(node):
            children[parent_name].append(child_name)
    for key in children:
        children[key].sort()
    return children


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    """校验 source、mux.source 等前级引用与输出名。

    Raises:
        ValueError: 引用节点不存在或输出名非法时。
    """
    validate_nodes_source_refs(nodes)
    from collections import deque

    children = build_children_map(nodes)
    pending = {name: len(upstream_peer_names(node)) for name, node in nodes.items()}
    queue = deque(name for name, count in pending.items() if count == 0)
    while queue:
        name = queue.popleft()
        for child in children[name]:
            pending[child] -= 1
            if pending[child] == 0:
                queue.append(child)
    remaining = {name for name, count in pending.items() if count > 0}
    if remaining:
        current = next(name for name in nodes if name in remaining)
        chain = []
        while current not in chain:
            chain.append(current)
            current = next(
                peer
                for peer in upstream_peer_names(nodes[current])
                if peer in remaining
            )
        cycle = chain[chain.index(current) :] + [current]
        raise ValueError("nodes.source 存在循环引用: " + " -> ".join(cycle))

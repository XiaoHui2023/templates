from __future__ import annotations

import re
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class NodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="记录标识。")


class GateNode(NodeBase):
    kind: Literal["gate"] = "gate"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class DtoNode(NodeBase):
    kind: Literal["dto"] = "dto"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"
    targets: List[str] = Field(
        ...,
        min_length=1,
        description="可驱动的下游器件名列表，须为本 tree nodes 中的 name。",
    )


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    targets: List[str] = Field(
        ...,
        min_length=1,
        description="可驱动的下游器件名列表，须为本 tree nodes 中的 name。",
    )


class ClockNode(NodeBase):
    kind: Literal["clock"] = "clock"
    source: str = Field(..., min_length=1, description="输入连线名。")
    freq: Optional[str] = Field(None, description="频率说明字符串，可选。")


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        ...,
        min_length=1,
        description="多路输入：键为图上输入标签字符串，值为对端器件名。",
    )
    target: str = Field(..., min_length=1, description="输出连线名。")

    @model_validator(mode="after")
    def _validate_mux_source_keys(self) -> MuxNode:
        if not self.source:
            raise ValueError(f"mux 节点 {self.name!r} 的 source 不得为空")
        return self


Node = Annotated[
    Union[
        GateNode,
        DivNode,
        DtoNode,
        InvNode,
        ClockSourceNode,
        PllNode,
        ClockNode,
        MuxNode,
    ],
    Field(discriminator="kind"),
]


class Tree(BaseModel):
    name: str = Field(..., min_length=1, description="时钟树名，兼作展开后 SV 类型名片段与建树函数名片段。")
    nodes: List[Node] = Field(..., min_length=1, description="本棵时钟树的节点列表。")
    settings: dict[str, int] = Field(
        default_factory=dict,
        description="本树设置项取值，键须与根配置 setting_defs 中各项 name 一致。",
    )

    @model_validator(mode="after")
    def _validate_name(self) -> Tree:
        if not _SV_ID.match(self.name):
            raise ValueError(
                f"tree.name {self.name!r} 须为合法 SystemVerilog 标识符片段"
            )
        return self


def _peer_names(node: Node) -> List[str]:
    if node.kind in ("source", "pll"):
        return list(node.targets)
    if node.kind == "mux":
        return list(node.source.values())
    return []


def validate_nodes_graph(nodes: List[Node]) -> None:
    """校验节点名唯一性与 targets / mux.source 对端名引用。

    Raises:
        ValueError: 节点名重复，或对端器件名不在 nodes.name 集合中时。
    """
    names = [n.name for n in nodes]
    if len(names) != len(set(names)):
        dup = {x for x in names if names.count(x) > 1}
        raise ValueError(f"nodes.name 须唯一，重复: {sorted(dup)}")

    known = set(names)
    for node in nodes:
        for peer in _peer_names(node):
            if peer not in known:
                raise ValueError(
                    f"节点 {node.name!r} 引用对端器件名 {peer!r} "
                    f"不在 nodes 的 name 集合中"
                )

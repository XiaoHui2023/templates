from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

PllKind = Literal["PLL_TCI", "PLL_SC", "PLL_DW"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="前级器件名。")
    key: Optional[int] = Field(None, description="mux 输入选择键；非 mux 为 null。")


class NodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="记录标识。")
    path: str = Field(
        "",
        description="对应信号在 DUT 上的实例层次路径；留空则不接 interface.in，out 任一变化 uvm_fatal。",
    )
    allow_bad_duty: bool = Field(
        False,
        description="为真时放宽占空比检查。",
    )
    freq: Optional[int] = Field(
        None,
        ge=1,
        description="典型频率 Hz；用于 source、clk、pll 的 tree 软约束。",
    )
    sources: List[SourceRef] = Field(
        default_factory=list,
        description="建树时由校验推导的前级列表；配置中勿填。",
    )

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not value:
            return value
        for seg in value.split("."):
            if not _SV_ID.match(seg):
                raise ValueError(
                    f"path 段 {seg!r} 须为合法 SystemVerilog 标识符，完整 path: {value!r}"
                )
        return value

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return int(value)


class GateNode(NodeBase):
    kind: Literal["gate"] = "gate"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")
    div_ratio: int = Field(1, ge=1, description="分频比。")


class DtoNode(NodeBase):
    kind: Literal["dto"] = "dto"
    source: str = Field(..., min_length=1, description="输入连线名。")
    target: str = Field(..., min_length=1, description="输出连线名。")
    div_ratio: int = Field(1, ge=1, description="分频比。")


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
    pll_kind: PllKind = Field("PLL_TCI", description="PLL 型号枚举名。")


class ClkNode(NodeBase):
    kind: Literal["clk"] = "clk"
    source: str = Field(..., min_length=1, description="输入连线名。")


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        ...,
        min_length=1,
        description="多路输入：键为图上输入标签字符串，值为对端器件名。",
    )
    target: str = Field(..., min_length=1, description="输出连线名。")
    sel: Optional[int] = Field(
        None,
        description="选择值；省略时取本 tree settings 中 pll_sel，若无则为 0。",
    )

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
        ClkNode,
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

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_node_kinds(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            return data
        normalized = []
        for item in nodes:
            if isinstance(item, dict) and item.get("kind") == "clock":
                item = {**item, "kind": "clk"}
            normalized.append(item)
        return {**data, "nodes": normalized}

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


def _driver_from_wire(wire: str, sink: str, known: set[str]) -> Optional[str]:
    prefix = "w_"
    suffix = f"_{sink}"
    if not wire.startswith(prefix) or not wire.endswith(suffix):
        return None
    driver = wire[len(prefix) : -len(suffix)]
    if not driver or not _SV_ID.match(driver):
        return None
    return driver if driver in known else None


def _build_sources(node: Node, known: set[str]) -> List[SourceRef]:
    if node.kind == "mux":
        return [
            SourceRef(name=peer, key=int(key))
            for key, peer in node.source.items()
        ]
    if node.kind in ("source", "pll"):
        return []
    wire = node.source
    driver = _driver_from_wire(wire, node.name, known)
    if driver is None:
        raise ValueError(
            f"节点 {node.name!r} 的输入连线 {wire!r} 须形如 w_<驱动器件>_{node.name}"
        )
    return [SourceRef(name=driver)]


def enrich_tree_nodes(
    nodes: List[Node],
    *,
    settings: dict[str, int],
) -> List[Node]:
    known = {n.name for n in nodes}
    enriched: List[Node] = []
    for node in nodes:
        updates: dict[str, Any] = {
            "sources": _build_sources(node, known),
        }
        if node.kind == "mux" and node.sel is None:
            updates["sel"] = settings.get("pll_sel", 0)
        enriched.append(node.model_copy(update=updates))
    return enriched


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
        if node.kind not in ("source", "pll", "mux"):
            if _driver_from_wire(node.source, node.name, known) is None:
                raise ValueError(
                    f"节点 {node.name!r} 的输入连线 {node.source!r} "
                    f"须形如 w_<驱动器件>_{node.name}"
                )

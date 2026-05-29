from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from reg_paths import (
    DIV_REG_KEYS,
    DTO_REG_KEYS,
    PLL_KIND_TO_SV,
    normalize_pll_kind,
    validate_optional_reg,
    validate_pll_regs_exact,
    validate_regs_exact,
)

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

PllKind = Literal["tci", "sc", "dw"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="前级节点名，与 tree 成员名一致；模板展开为 SV 句柄赋值右端。",
    )
    key: Optional[int] = Field(
        None,
        description="mux 的 to_source 键；非 mux 为 null。",
    )


class NodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="记录标识；YAML 以 nodes 字典键为准，勿在节点内重复填写。")
    path: str = Field(
        "",
        description="RTL 层次路径，仅用于 connect 展开时 force 到 DUT；不写入节点类成员。留空则不生成 interface、节点 vif 为 null。",
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
        description="校验后推导的前级连线；非 mux 一项写 source，mux 多项写 to_source；配置中勿填。",
    )
    mux_sel_inside: str = Field(
        "",
        description="mux 的 source 键展开为 sel inside 集合字面量，如 0, 1；非 mux 为空。",
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
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    target: str = Field(..., min_length=1, description="输出连线名。")
    reg: str = Field(
        "",
        description="可选；RAL 点分路径，绑定到 f_reg；可带 [n] 或 [msb:lsb] 指定 field 内比特切片。",
    )

    @model_validator(mode="after")
    def _validate_gate_reg(self) -> GateNode:
        validate_optional_reg(self.reg, node_name=self.name, kind="gate")
        return self


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    target: str = Field(..., min_length=1, description="输出连线名。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须为 rst、load、div，值为各 field 的 RAL 点分路径，可带比特范围后缀。",
    )

    @model_validator(mode="after")
    def _validate_div_regs(self) -> DivNode:
        validate_regs_exact(
            self.regs, DIV_REG_KEYS, node_name=self.name, kind="div"
        )
        return self


class DtoNode(NodeBase):
    kind: Literal["dto"] = "dto"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    target: str = Field(..., min_length=1, description="输出连线名。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须为 rstn、load、bypass、step，值为各 field 的 RAL 点分路径，可带比特范围后缀。",
    )

    @model_validator(mode="after")
    def _validate_dto_regs(self) -> DtoNode:
        validate_regs_exact(
            self.regs, DTO_REG_KEYS, node_name=self.name, kind="dto"
        )
        return self


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    target: str = Field(..., min_length=1, description="输出连线名。")


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"
    targets: List[str] = Field(
        ...,
        min_length=1,
        description="可驱动的下游器件名列表，须为本 tree nodes 的键。",
    )


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    targets: List[str] = Field(
        ...,
        min_length=1,
        description="可驱动的下游器件名列表，须为本 tree nodes 的键。",
    )
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw，大小写不限。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须与 pll_kind 允许集合完全一致，值为 RAL 点分路径，可带 [n] 或 [msb:lsb] 后缀。",
    )

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_pll_kind(cls, value: object) -> str:
        return normalize_pll_kind(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sv_pll_class(self) -> str:
        return PLL_KIND_TO_SV[self.pll_kind]

    @model_validator(mode="after")
    def _validate_pll_regs(self) -> PllNode:
        validate_pll_regs_exact(self.regs, self.pll_kind, node_name=self.name)
        return self


class ClkNode(NodeBase):
    kind: Literal["clk"] = "clk"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        default_factory=dict,
        description="多路输入：键为图上输入标签字符串，值为对端器件名；可省略或留空表示暂无输入。",
    )
    target: str = Field(..., min_length=1, description="输出连线名。")
    reg: str = Field(
        "",
        description="可选；RAL 点分路径，绑定到 f_reg；可带 [n] 或 [msb:lsb] 指定 field 内比特切片。",
    )

    @model_validator(mode="after")
    def _validate_mux(self) -> MuxNode:
        validate_optional_reg(self.reg, node_name=self.name, kind="mux")
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
    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="本棵时钟树的节点表，键为节点 name，节点体内勿填 name。",
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
                if not isinstance(item, dict):
                    as_dict[str(item)] = item
                    continue
                if item.get("kind") == "clock":
                    item = {**item, "kind": "clk"}
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
                raise ValueError(
                    f"nodes 键 {key!r} 须为合法 SystemVerilog 标识符"
                )
            if isinstance(item, dict):
                if item.get("kind") == "clock":
                    item = {**item, "kind": "clk"}
                inner_name = item.get("name")
                if inner_name is not None and inner_name != key:
                    raise ValueError(
                        f"nodes[{key!r}] 内 name {inner_name!r} 须与键一致或省略"
                    )
                item = {k: v for k, v in item.items() if k != "name"}
                normalized[key] = {**item, "name": key}
            else:
                normalized[key] = item
        return {**data, "nodes": normalized}

    @model_validator(mode="after")
    def _validate_name(self) -> Tree:
        if not _SV_ID.match(self.name):
            raise ValueError(
                f"tree.name {self.name!r} 须为合法 SystemVerilog 标识符片段"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nodes_ordered(self) -> List[Node]:
        return list(self.nodes.values())

    @model_validator(mode="after")
    def _enrich_nodes(self) -> Tree:
        validate_nodes_graph(self.nodes)
        enriched = enrich_tree_nodes(self.nodes)
        self.nodes = enriched
        return self


def _peer_names(node: Node) -> List[str]:
    if node.kind in ("source", "pll"):
        return list(node.targets)
    if node.kind == "mux":
        return list(node.source.values())
    if node.kind in ("gate", "div", "dto", "inv", "clk"):
        return [node.source]
    return []


def _build_sources(node: Node, known: set[str]) -> List[SourceRef]:
    if node.kind == "mux":
        refs = [
            SourceRef(name=peer, key=int(key))
            for key, peer in node.source.items()
        ]
        for ref in refs:
            if ref.name not in known:
                raise ValueError(
                    f"mux 节点 {node.name!r} 的对端 {ref.name!r} 须为本 tree nodes 的键"
                )
        return refs
    if node.kind in ("source", "pll"):
        return []
    peer = node.source
    if peer not in known:
        raise ValueError(
            f"节点 {node.name!r} 的 source {peer!r} 须为本 tree nodes 的键"
        )
    return [SourceRef(name=peer)]


def enrich_tree_nodes(
    nodes: Dict[str, Node],
) -> Dict[str, Node]:
    known = set(nodes.keys())
    enriched: Dict[str, Node] = {}
    for key, node in nodes.items():
        if node.name != key:
            raise ValueError(
                f"nodes[{key!r}] 的 name 字段 {node.name!r} 须与字典键一致"
            )
        updates: dict[str, Any] = {
            "sources": _build_sources(node, known),
        }
        if node.kind == "mux":
            keys = sorted(int(k) for k in node.source.keys())
            updates["mux_sel_inside"] = ", ".join(str(k) for k in keys)
        enriched[key] = node.model_copy(update=updates)
    return enriched


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    """校验 targets、source、mux.source 等对端节点名引用。

    Raises:
        ValueError: 对端节点名不在 nodes 键集合中时。
    """
    known = set(nodes.keys())
    for key, node in nodes.items():
        if node.name != key:
            raise ValueError(
                f"nodes[{key!r}] 的 name 字段 {node.name!r} 须与字典键一致"
            )
        for peer in _peer_names(node):
            if peer not in known:
                raise ValueError(
                    f"节点 {node.name!r} 引用对端节点名 {peer!r} "
                    f"不在 nodes 的键集合中"
                )

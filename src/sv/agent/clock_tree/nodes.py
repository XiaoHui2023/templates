from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    TypeAdapter,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

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

    _name: str = PrivateAttr(default="")

    @computed_field(  # type: ignore[prop-decorator]
        description="等于 Tree.nodes 字典键；YAML 体内与 model_validate 不可传入。",
    )
    @property
    def name(self) -> str:
        return self._name

    path: str = Field(
        "",
        description="RTL 层次路径，供 tree_connection 例化 interface 的 in 端口；不写入节点类成员。留空则不生成 interface、节点 vif 为 null。",
    )
    freq: Optional[int] = Field(
        None,
        ge=1,
        description="典型频率 Hz；用于 source、clk、pll 的 tree 软约束。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="由 source 或 mux.source 推导；YAML 与 model_validate 不可传入。",
    )
    @property
    def sources(self) -> List[SourceRef]:
        if self.kind == "mux":
            return [
                SourceRef(name=peer, key=int(key))
                for key, peer in self.source.items()
            ]
        if self.kind == "source":
            return []
        return [SourceRef(name=self.source)]

    @computed_field(  # type: ignore[prop-decorator]
        description="mux 的 source 键展开为 sel inside 集合字面量；YAML 与 model_validate 不可传入。",
    )
    @property
    def mux_sel_inside(self) -> str:
        if self.kind != "mux":
            return ""
        keys = sorted(int(k) for k in self.source.keys())
        return ", ".join(str(k) for k in keys)

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
    reg: str = Field(
        "",
        description="可选；寄存器模型点分路径，绑定到 f_reg；可带 [n] 或 [msb:lsb] 指定 field 内比特切片。",
    )

    @model_validator(mode="after")
    def _validate_gate_reg(self, info: ValidationInfo) -> GateNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="gate"
        )
        return self


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须为 rst、load、div，值为各 field 的 寄存器模型点分路径，可带比特范围后缀。",
    )

    @model_validator(mode="after")
    def _validate_div_regs(self, info: ValidationInfo) -> DivNode:
        validate_regs_exact(
            self.regs,
            DIV_REG_KEYS,
            node_name=_validation_node_name(self, info),
            kind="div",
        )
        return self


class DtoNode(NodeBase):
    kind: Literal["dto"] = "dto"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须为 rstn、load、bypass、step，值为各 field 的 寄存器模型点分路径，可带比特范围后缀。",
    )

    @model_validator(mode="after")
    def _validate_dto_regs(self, info: ValidationInfo) -> DtoNode:
        validate_regs_exact(
            self.regs,
            DTO_REG_KEYS,
            node_name=_validation_node_name(self, info),
            kind="dto",
        )
        return self


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    source: str = Field(..., min_length=1, description="前级节点名，须为本 tree nodes 的键。")


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    source: str = Field(
        ...,
        min_length=1,
        description="参考时钟前级节点名，须为本 tree nodes 的键；config_reg 用其 frequence 计算分频。",
    )
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw，大小写不限。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="可选；非空时键须与 pll_kind 允许集合完全一致，值为 寄存器模型点分路径，可带 [n] 或 [msb:lsb] 后缀。",
    )

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_pll_kind(cls, value: object) -> str:
        return normalize_pll_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="由 pll_kind 映射的 SV 模型类名片段；YAML 与 model_validate 不可传入。",
    )
    @property
    def sv_pll_class(self) -> str:
        return PLL_KIND_TO_SV[self.pll_kind]

    @model_validator(mode="after")
    def _validate_pll_regs(self, info: ValidationInfo) -> PllNode:
        validate_pll_regs_exact(
            self.regs,
            self.pll_kind,
            node_name=_validation_node_name(self, info),
        )
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
    reg: str = Field(
        "",
        description="可选；寄存器模型点分路径，绑定到 f_reg；可带 [n] 或 [msb:lsb] 指定 field 内比特切片。",
    )

    @model_validator(mode="after")
    def _validate_mux(self, info: ValidationInfo) -> MuxNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="mux"
        )
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

_node_adapter: TypeAdapter[Node] = TypeAdapter(Node)


def _validation_node_name(node: NodeBase, info: ValidationInfo) -> str:
    key = (info.context or {}).get("node_name")
    if isinstance(key, str) and key:
        return key
    if node._name:
        return node._name
    raise ValueError("节点须在 Tree.nodes 字典键上下文内校验")


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="时钟树名，兼作展开后 SV 类型名片段与建树函数名片段。")
    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="本棵时钟树的节点表，键即节点名；节点体内勿填 name。",
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
            if isinstance(item, NodeBase):
                object.__setattr__(item, "_name", key)
                built[key] = item
                continue
            node = _node_adapter.validate_python(
                item, context={"node_name": key}
            )
            object.__setattr__(node, "_name", key)
            built[key] = node
        return built

    @model_validator(mode="after")
    def _validate_name(self) -> Tree:
        if not _SV_ID.match(self.name):
            raise ValueError(
                f"tree.name {self.name!r} 须为合法 SystemVerilog 标识符片段"
            )
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="nodes 值的有序列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def nodes_ordered(self) -> List[Node]:
        return list(self.nodes.values())

    @computed_field(  # type: ignore[prop-decorator]
        description="由各节点 source 反查；键为节点名，值为以其为前级的子节点名列表；YAML 不可传入。",
    )
    @property
    def children_by_node(self) -> Dict[str, List[str]]:
        return build_children_map(self.nodes)

    @model_validator(mode="after")
    def _validate_nodes_graph(self) -> Tree:
        validate_nodes_graph(self.nodes)
        return self


def upstream_peer_names(node: Node) -> List[str]:
    if node.kind == "mux":
        return list(node.source.values())
    if node.kind in ("gate", "div", "dto", "inv", "clk", "pll"):
        return [node.source]
    return []


def build_children_map(nodes: Dict[str, Node]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {key: [] for key in nodes}
    for child_name, node in nodes.items():
        for parent_name in upstream_peer_names(node):
            children[parent_name].append(child_name)
    for key in children:
        children[key].sort()
    return children


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    """校验 source、mux.source 等对端节点名引用。

    Raises:
        ValueError: 对端节点名不在 nodes 键集合中时。
    """
    known = set(nodes.keys())
    for key, node in nodes.items():
        if node.name != key:
            raise ValueError(
                f"nodes[{key!r}] 的 name 字段 {node.name!r} 须与字典键一致"
            )
        for peer in upstream_peer_names(node):
            if peer not in known:
                raise ValueError(
                    f"节点 {node.name!r} 引用对端节点名 {peer!r} "
                    f"不在 nodes 的键集合中"
                )

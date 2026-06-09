from __future__ import annotations

import re
from dataclasses import dataclass
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
    sv_node_access,
    validate_optional_reg,
    validate_pll_regs_exact,
    validate_regs_exact,
)

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SOURCE_ENDPOINT = re.compile(
    r"^(?P<device>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<idx>\d+)\])?$"
)

PllKind = Literal["tci", "sc", "dw", "inno"]


def parse_source_endpoint(raw: str, *, ctx: str) -> tuple[str, int]:
    text = raw.strip()
    match = _SOURCE_ENDPOINT.match(text)
    if not match:
        raise ValueError(
            f"{ctx} 前级引用 {raw!r} 须为器件名或 器件名[输出序号] 形式"
        )
    device = match.group("device")
    idx_text = match.group("idx")
    out_idx = int(idx_text) if idx_text is not None else 0
    return device, out_idx


def node_output_count(node: Node) -> int:
    if node.kind == "pll":
        return node.output_count
    return 1


@dataclass(frozen=True)
class SvNodeSlot:
    """展开到 SV 的单个节点实例槽位。"""

    node_key: str
    group_id: int
    access: str


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="前级器件名，与 tree.nodes 字典键一致。",
    )
    out_idx: int = Field(
        0,
        ge=0,
        description="前级器件输出序号；省略 `[序号]` 时等价于 0。",
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

    @computed_field(  # type: ignore[prop-decorator]
        description="SV 侧是否为多路输出静态数组；YAML 不可传入。",
    )
    @property
    def sv_is_array(self) -> bool:
        return node_output_count(self) > 1  # type: ignore[arg-type]

    path: str = Field(
        "",
        description="RTL 层次路径，按 `.` 分隔。",
    )
    freq: Optional[int] = Field(
        None,
        ge=1,
        description="典型频率，单位 Hz。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="由 source 或 mux.source 推导；YAML 与 model_validate 不可传入。",
    )
    @property
    def sources(self) -> List[SourceRef]:
        if self.kind == "mux":
            refs: List[SourceRef] = []
            for key, peer in self.source.items():
                device, out_idx = parse_source_endpoint(peer, ctx="mux.source")
                refs.append(SourceRef(name=device, out_idx=out_idx, key=int(key)))
            return refs
        if self.kind == "source":
            return []
        device, out_idx = parse_source_endpoint(self.source, ctx="source")
        return [SourceRef(name=device, out_idx=out_idx)]

    @computed_field(  # type: ignore[prop-decorator]
        description="mux 的 source 键最大值，供 SV max_sel；YAML 与 model_validate 不可传入。",
    )
    @property
    def mux_max_sel(self) -> int:
        if self.kind != "mux" or not self.source:
            return 0
        return max(int(k) for k in self.source.keys())

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not value:
            return value
        for seg in value.split("."):
            if not _SV_ID.match(seg):
                raise ValueError(
                    f"path 段 {seg!r} 须为合法 SystemVerilog 名字，完整 path: {value!r}"
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
    source: str = Field(..., min_length=1, description="前级引用。")
    reg: str = Field(
        "",
        description="寄存器模型路径。",
    )

    @model_validator(mode="after")
    def _validate_gate_reg(self, info: ValidationInfo) -> GateNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="gate"
        )
        return self


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    source: str = Field(..., min_length=1, description="前级引用。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键为 rst、load、div，值为寄存器模型路径。",
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
    source: str = Field(..., min_length=1, description="前级引用。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键为 rst、load、bypass、step，值为寄存器模型路径。",
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
    source: str = Field(..., min_length=1, description="前级引用。")


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    source: str = Field(
        ...,
        min_length=1,
        description="参考时钟前级引用。",
    )
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw、inno，大小写不限。")
    output_count: int = Field(
        1,
        ge=1,
        description="有几路输出。仅 inno 可用。",
    )
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="逻辑名到寄存器模型路径；非空时键须与 pll_kind、output_count 允许集合一致。",
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
        if self.output_count > 1 and self.pll_kind != "inno":
            raise ValueError(
                f"pll 节点 {self.name!r} output_count 为 {self.output_count} 时 "
                f"pll_kind 须为 inno，得到 {self.pll_kind!r}"
            )
        validate_pll_regs_exact(
            self.regs,
            self.pll_kind,
            node_name=_validation_node_name(self, info),
            output_count=self.output_count,
        )
        return self


class ClkNode(NodeBase):
    kind: Literal["clk"] = "clk"
    source: str = Field(..., min_length=1, description="前级引用。")


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        default_factory=dict,
        description="输入标签到前级引用的映射。",
    )
    reg: str = Field(
        "",
        description="寄存器模型路径。",
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

    name: str = Field(..., min_length=1, description="时钟树名称。")
    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键为节点名。",
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
                    f"nodes 键 {key!r} 须为合法 SystemVerilog 名字"
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
                f"tree.name {self.name!r} 须为合法 SystemVerilog 类型名片段"
            )
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="nodes 值的有序列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def nodes_ordered(self) -> List[Node]:
        return list(self.nodes.values())

    @computed_field(  # type: ignore[prop-decorator]
        description="展开到 SV 的节点实例槽位；多路输出器件按路展开；YAML 不可传入。",
    )
    @property
    def sv_slots(self) -> List[SvNodeSlot]:
        slots: List[SvNodeSlot] = []
        for key, node in self.nodes.items():
            count = node_output_count(node)
            for group_id in range(count):
                slots.append(
                    SvNodeSlot(
                        node_key=key,
                        group_id=group_id,
                        access=sv_node_access(key, group_id, count),
                    )
                )
        return slots

    def source_sv_access(self, ref: SourceRef) -> str:
        peer = self.nodes[ref.name]
        return sv_node_access(ref.name, ref.out_idx, node_output_count(peer))

    @computed_field(  # type: ignore[prop-decorator]
        description="由各节点 source 反查；键为器件名，值为以其为前级的子节点名列表；YAML 不可传入。",
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
        return [
            parse_source_endpoint(peer, ctx="mux.source")[0]
            for peer in node.source.values()
        ]
    if node.kind in ("gate", "div", "dto", "inv", "clk", "pll"):
        device, _out_idx = parse_source_endpoint(node.source, ctx="source")
        return [device]
    return []


def build_children_map(nodes: Dict[str, Node]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {key: [] for key in nodes}
    for child_name, node in nodes.items():
        for parent_name in upstream_peer_names(node):
            children[parent_name].append(child_name)
    for key in children:
        children[key].sort()
    return children


def _validate_source_ref(
    raw: str,
    nodes: Dict[str, Node],
    *,
    ctx: str,
) -> None:
    device, out_idx = parse_source_endpoint(raw, ctx=ctx)
    if device not in nodes:
        raise ValueError(
            f"{ctx} 引用器件 {device!r} 不在 nodes 中"
        )
    peer = nodes[device]
    count = node_output_count(peer)
    if count <= 1 and out_idx != 0:
        raise ValueError(
            f"{ctx} 引用 {raw!r}：器件 {device!r} 仅单路输出，不可使用 [{out_idx}]"
        )
    if out_idx >= count:
        raise ValueError(
            f"{ctx} 引用 {raw!r}：输出序号 {out_idx} 超出器件 {device!r} "
            f"的 output_count {count}"
        )


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    """校验 source、mux.source 等前级引用与输出序号。

    Raises:
        ValueError: 引用节点不存在或输出序号非法时。
    """
    for key, node in nodes.items():
        if node.name != key:
            raise ValueError(
                f"nodes[{key!r}] 的 name 字段 {node.name!r} 须与字典键一致"
            )
        if node.kind == "mux":
            for mux_key, peer in node.source.items():
                _validate_source_ref(
                    peer,
                    nodes,
                    ctx=f"节点 {node.name!r} mux.source[{mux_key!r}]",
                )
        elif node.kind in ("gate", "div", "dto", "inv", "clk", "pll"):
            _validate_source_ref(
                node.source,
                nodes,
                ctx=f"节点 {node.name!r} source",
            )

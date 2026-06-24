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
    CPU_GATE_OUTPUT_GROUPS,
    DIV_KIND_TO_SV,
    INV_KIND_TO_SV,
    PLL_KIND_TO_SV,
    SOURCE_KIND_TO_SV,
    _FIXED_ZERO_FREQ_SOURCE_KINDS,
    div_reg_keys_for_kind,
    node_path_connectable,
    normalize_cell_kind,
    normalize_div_kind,
    normalize_inv_kind,
    normalize_pll_kind,
    normalize_source_kind,
    node_output_groups,
    primary_output_group,
    sv_node_access,
    validate_optional_reg,
    validate_pll_regs_exact,
    validate_regs_exact,
)

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SOURCE_ENDPOINT = re.compile(
    r"^(?P<device>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<group>[^\]]+)\])?$"
)
_GROUP_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_NODE_KIND_ALIASES: dict[str, str] = {
    "clock": "clk",
}

_LEGACY_DIV_KINDS = frozenset({"div", "div_n", "dto", "dto_n", "cpu_gate", "div_r"})

PllKind = Literal["tci", "sc", "dw", "inno"]
DivKind = Literal["div", "div_n", "dto", "dto_n", "cpu_gate", "div_r"]
InvKind = Literal["inv", "mux_inv", "inv_cell"]
SourceKind = Literal["source", "gate", "vdd", "gnd"]


def _normalize_node_item(item: dict[str, Any]) -> dict[str, Any]:
    kind = item.get("kind")
    canonical = _NODE_KIND_ALIASES.get(kind)
    if canonical is not None:
        return {**item, "kind": canonical}
    if kind in _LEGACY_DIV_KINDS:
        div_kind = item.get("div_kind", kind)
        body = {k: v for k, v in item.items() if k != "kind"}
        return {**body, "kind": "div", "div_kind": div_kind}
    return item


def _coerce_required_freq(value: Any) -> int:
    if value is None or value == "":
        raise ValueError("须填写 freq")
    return int(value)


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def parse_source_endpoint(raw: str, *, ctx: str) -> tuple[str, str]:
    text = raw.strip()
    match = _SOURCE_ENDPOINT.match(text)
    if not match:
        raise ValueError(
            f"{ctx} 前级引用 {raw!r} 须为器件名或 器件名[输出名] 形式"
        )
    device = match.group("device")
    group_text = match.group("group")
    out_group = group_text if group_text is not None else ""
    if out_group and not _GROUP_KEY_RE.match(out_group):
        raise ValueError(
            f"{ctx} 前级引用 {raw!r} 中输出名 {out_group!r} "
            f"须为合法 SystemVerilog 名字"
        )
    return device, out_group


@dataclass(frozen=True)
class SvNodeSlot:
    """展开到 SV 的单个节点实例槽位。"""

    node_key: str
    group_id: str
    access: str


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="前级器件名，与 tree.nodes 字典键一致。",
    )
    out_group: str = Field(
        "",
        description="前级器件输出名；省略方括号时为空字符串，表示单路输出默认路。",
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
        return len(node_output_groups(self)) > 1  # type: ignore[arg-type]

    @computed_field(  # type: ignore[prop-decorator]
        description="多路输出名列表；单路节点为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        return []

    @computed_field(  # type: ignore[prop-decorator]
        description="多路输出时为首路输出名，单路为空字符串；YAML 不可传入。",
    )
    @property
    def primary_output_group(self) -> str:
        return primary_output_group(self)

    path: str = Field(
        "",
        description="RTL 层次路径，按 `.` 分隔。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="由 source 或 mux.source 推导；YAML 与 model_validate 不可传入。",
    )
    @property
    def sources(self) -> List[SourceRef]:
        if self.kind == "mux":
            refs: List[SourceRef] = []
            for key, peer in self.source.items():
                device, out_group = parse_source_endpoint(peer, ctx="mux.source")
                refs.append(SourceRef(name=device, out_group=out_group, key=int(key)))
            return refs
        if self.kind == "source":
            return []
        device, out_group = parse_source_endpoint(self.source, ctx="source")
        return [SourceRef(name=device, out_group=out_group)]

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
    div_kind: DivKind = Field(
        "div",
        description="分频器型号：div、div_n、dto、dto_n、cpu_gate、div_r，大小写不限。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")
    ratio: Optional[int] = Field(
        None,
        ge=1,
        description="分频比；div_r 必填；其余 div 省略表示随机化。",
    )
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键由 div_kind 决定：div/div_n 为 rst、load、div；"
        "dto/dto_n 为 rst、load、bypass、step；"
        "cpu_gate 为 rst、div；"
        "div_r 不可配置寄存器，须为空。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="cpu_gate 固定三路输出名；其余 div 为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        if self.div_kind == "cpu_gate":
            return list(CPU_GATE_OUTPUT_GROUPS)
        return []

    @field_validator("div_kind", mode="before")
    @classmethod
    def _normalize_div_kind(cls, value: object) -> str:
        return normalize_div_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="由 div_kind 映射的 SV 模型类名片段；YAML 与 model_validate 不可传入。",
    )
    @property
    def sv_div_class(self) -> str:
        return DIV_KIND_TO_SV[self.div_kind]

    @model_validator(mode="after")
    def _validate_div_regs(self, info: ValidationInfo) -> DivNode:
        if self.div_kind == "div_r":
            if self.ratio is None:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 div_r 时须填写 ratio"
                )
        elif self.ratio is not None:
            max_ratio = 64
            if self.div_kind == "cpu_gate":
                max_ratio = 32
            if self.ratio > max_ratio:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 {self.div_kind!r} 时 ratio 须不大于 {max_ratio}，"
                    f"得到 {self.ratio}"
                )
        validate_regs_exact(
            self.regs,
            div_reg_keys_for_kind(self.div_kind),
            node_name=_validation_node_name(self, info),
            kind=f"div({self.div_kind})",
        )
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="trees 构造写入 ratio；省略时为 -1；YAML 不可传入。",
    )
    @property
    def div_init_ratio(self) -> int:
        return -1 if self.ratio is None else self.ratio

    @computed_field(  # type: ignore[prop-decorator]
        description="ratio 非 div_base::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def div_trees_emit_unfix_ratio(self) -> bool:
        return self.ratio is not None


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    inv_kind: InvKind = Field(
        "inv",
        description="反相器型号：inv、mux_inv、inv_cell，大小写不限。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")
    reg: str = Field(
        "",
        description="反相/直通控制寄存器模型路径。",
    )

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_inv_kind(cls, value: object) -> str:
        return normalize_inv_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="由 inv_kind 映射的 SV 模型类名片段；YAML 与 model_validate 不可传入。",
    )
    @property
    def sv_inv_class(self) -> str:
        return INV_KIND_TO_SV[self.inv_kind]

    @model_validator(mode="after")
    def _validate_inv_reg(self, info: ValidationInfo) -> InvNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="inv"
        )
        return self


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"
    source_kind: SourceKind = Field(
        "source",
        description="输入源型号：source、gate、vdd、gnd，大小写不限。",
    )
    freq: int = Field(
        0,
        ge=0,
        description="典型频率，单位 Hz；vdd、gnd 固定为 0 或可省略。",
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> str:
        return normalize_source_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="由 source_kind 映射的 SV 模型类名片段；YAML 与 model_validate 不可传入。",
    )
    @property
    def sv_source_class(self) -> str:
        return SOURCE_KIND_TO_SV[self.source_kind]

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0
        return int(value)

    @model_validator(mode="after")
    def _validate_source_freq(self) -> ClockSourceNode:
        if self.source_kind in _FIXED_ZERO_FREQ_SOURCE_KINDS:
            if self.freq != 0:
                raise ValueError(
                    f"source_kind 为 {self.source_kind} 时 freq 只能是 0 或省略"
                )
            return self
        if self.freq < 1:
            raise ValueError(
                "source_kind 为 source、gate 时须填写大于 0 的 freq"
            )
        return self


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    freq: int = Field(..., ge=1, description="典型频率，单位 Hz。")

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        return _coerce_required_freq(value)
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

    @computed_field(  # type: ignore[prop-decorator]
        description="多路 inno 时为 0、1 等字符串路名；单路为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        if self.output_count <= 1:
            return []
        return [str(i) for i in range(self.output_count)]

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
            output_groups=self.output_groups,
        )
        return self


class CellNode(NodeBase):
    kind: Literal["cell"] = "cell"
    cell_kind: str = Field(
        "cell",
        min_length=1,
        description="配置型号，任意非空字符串；仅作记录，仿真行为相同。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")

    @field_validator("cell_kind", mode="before")
    @classmethod
    def _normalize_cell_kind(cls, value: object) -> str:
        return normalize_cell_kind(value)


class ClkNode(NodeBase):
    kind: Literal["clk"] = "clk"
    freq: Optional[int] = Field(
        default=None,
        description="典型频率，单位 Hz；省略表示频率与开关均不指定；"
        "正数同时指定频率与使能；负数仅不约束 _resolved_freq。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")
    always_active: bool = Field(
        default=False,
        description="为真时该时钟节点全程保持有效；low_power 不关断。",
    )

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_optional_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="trees 构造写入 frequence；省略 freq 时为 -1；YAML 不可传入。",
    )
    @property
    def clk_init_frequence(self) -> int:
        return -1 if self.freq is None else self.freq

    @computed_field(  # type: ignore[prop-decorator]
        description="trees 构造写入 enabled；省略 freq 时为 -1，否则为 1；YAML 不可传入。",
    )
    @property
    def clk_init_enabled(self) -> int:
        return -1 if self.freq is None else 1

    @computed_field(  # type: ignore[prop-decorator]
        description="frequence 非 clk::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def clk_trees_emit_frequence(self) -> bool:
        return self.freq is not None and self.freq != -1

    @computed_field(  # type: ignore[prop-decorator]
        description="enabled 非 clk::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def clk_trees_emit_enabled(self) -> bool:
        return self.freq is not None

    @computed_field(  # type: ignore[prop-decorator]
        description="unfix_frequence 非 clk::new 默认 1 时为真；YAML 不可传入。",
    )
    @property
    def clk_trees_emit_unfix_frequence(self) -> bool:
        return self.freq is not None and self.freq > 0

    @computed_field(  # type: ignore[prop-decorator]
        description="unfix_enabled 非 clk::new 默认 1 时为真；YAML 不可传入。",
    )
    @property
    def clk_trees_emit_unfix_enabled(self) -> bool:
        return self.freq is not None

    @model_validator(mode="after")
    def _validate_clk_freq(self) -> ClkNode:
        if self.freq is not None and self.freq == 0:
            raise ValueError(
                f"clk 节点 {self.name!r} freq 为 0 非法；"
                f"正频率应大于等于 1，不约束请省略或填负数"
            )
        return self


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    source: Dict[str, str] = Field(
        default_factory=dict,
        description="输入标签到前级引用的映射。",
    )
    sel: Optional[int] = Field(
        None,
        ge=0,
        description="mux 选择值；省略表示随机化。",
    )
    reg: str = Field(
        "",
        description="寄存器模型路径。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="trees 构造写入 sel；省略时为 -1；YAML 不可传入。",
    )
    @property
    def mux_init_sel(self) -> int:
        return -1 if self.sel is None else self.sel

    @computed_field(  # type: ignore[prop-decorator]
        description="sel 非 mux::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def mux_trees_emit_unfix_sel(self) -> bool:
        return self.sel is not None

    @model_validator(mode="after")
    def _validate_mux(self, info: ValidationInfo) -> MuxNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="mux"
        )
        if self.sel is not None and self.sel > self.mux_max_sel:
            raise ValueError(
                f"mux 节点 {_validation_node_name(self, info)!r} "
                f"sel 为 {self.sel} 超出 source 键范围 0～{self.mux_max_sel}"
            )
        return self


Node = Annotated[
    Union[
        GateNode,
        DivNode,
        InvNode,
        ClockSourceNode,
        PllNode,
        CellNode,
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
    module_path: str = Field(
        "",
        description="该树可测量 RTL 模块的层次路径，按 `.` 分隔；"
        "非空时仅 path 等于此路径或以其为前缀的节点接测量 interface；"
        "省略或空字符串表示不按模块过滤。",
    )
    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键为节点名。",
    )

    @field_validator("module_path")
    @classmethod
    def _validate_module_path(cls, value: str) -> str:
        if not value:
            return value
        for seg in value.split("."):
            if not _SV_ID.match(seg):
                raise ValueError(
                    f"module_path 段 {seg!r} 须为合法 SystemVerilog 名字，"
                    f"完整 module_path: {value!r}"
                )
        return value

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
                item = _normalize_node_item(item)
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
                item = _normalize_node_item(item)
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
            groups = node_output_groups(node)
            if not groups:
                slots.append(
                    SvNodeSlot(
                        node_key=key,
                        group_id="",
                        access=sv_node_access(key, "", groups),
                    )
                )
                continue
            for group_id in groups:
                slots.append(
                    SvNodeSlot(
                        node_key=key,
                        group_id=group_id,
                        access=sv_node_access(key, group_id, groups),
                    )
                )
        return slots

    @computed_field(  # type: ignore[prop-decorator]
        description="module_path 范围内且 path 非空的 sv_slots；用于测量 interface 与 tree_connection；YAML 不可传入。",
    )
    @property
    def connectable_slots(self) -> List[SvNodeSlot]:
        return [
            slot
            for slot in self.sv_slots
            if node_path_connectable(self, self.nodes[slot.node_key])
        ]

    def source_sv_access(self, ref: SourceRef) -> str:
        peer = self.nodes[ref.name]
        groups = node_output_groups(peer)
        return sv_node_access(ref.name, ref.out_group, groups)

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
    if node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
        device, _out_group = parse_source_endpoint(node.source, ctx="source")
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
    device, out_group = parse_source_endpoint(raw, ctx=ctx)
    if device not in nodes:
        raise ValueError(
            f"{ctx} 引用器件 {device!r} 不在 nodes 中"
        )
    peer = nodes[device]
    groups = node_output_groups(peer)
    if not groups:
        if out_group:
            raise ValueError(
                f"{ctx} 引用 {raw!r}：器件 {device!r} 仅单路输出，不可写方括号"
            )
        return
    if not out_group:
        raise ValueError(
            f"{ctx} 引用 {raw!r}：器件 {device!r} 有多路输出，须写 器件名[输出名]"
        )
    if out_group not in groups:
        raise ValueError(
            f"{ctx} 引用 {raw!r}：输出名 {out_group!r} 不在器件 {device!r} "
            f"允许集合 {groups!r} 中"
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
        elif node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
            _validate_source_ref(
                node.source,
                nodes,
                ctx=f"节点 {node.name!r} source",
            )

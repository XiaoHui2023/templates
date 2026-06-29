from __future__ import annotations

import re
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from reg_paths import (
    CPU_GATE_OUTPUT_GROUPS,
    INNO_PLL_OUTPUT_GROUPS,
    _FIXED_ZERO_FREQ_SOURCE_KINDS,
    div_reg_keys_for_kind,
    node_output_groups,
    normalize_cell_kind,
    normalize_div_kind,
    normalize_inv_kind,
    normalize_pll_kind,
    normalize_source_kind,
    primary_output_group,
    validate_optional_reg,
    validate_pll_regs_exact,
    validate_regs_exact,
)

PllKind = Literal["tci", "sc", "dw", "inno"]
DivKind = Literal["div", "div_n", "dto", "dto_n", "cpu_gate", "div_r"]
InvKind = Literal["inv", "inv_mux", "inv_cell"]
SourceKind = Literal["source", "pad", "vdd", "gnd"]

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SOURCE_ENDPOINT = re.compile(
    r"^(?P<device>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<group>[^\]]+)\])?$"
)
_GROUP_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_NODE_KIND_ALIASES: dict[str, str] = {
    "clock": "clk",
}
_LEGACY_DIV_KINDS = frozenset({"div", "div_n", "dto", "dto_n", "cpu_gate", "div_r"})
_CPU_GATE_RATIOS = frozenset({2, 3, 4, 6})
_SOURCE_REF_KINDS = frozenset({"gate", "div", "inv", "cell", "clk", "pll"})


def normalize_source_endpoint_input(raw: Any, *, ctx: str) -> str:
    if isinstance(raw, str):
        return raw.strip()
    raise ValueError(f"{ctx} 前级引用 {raw!r} 须为字符串")


def _normalize_node_item(item: dict[str, Any]) -> dict[str, Any]:
    kind = item.get("kind")
    if kind in _LEGACY_DIV_KINDS:
        div_kind = item.get("div_kind", kind)
        body = {k: v for k, v in item.items() if k != "kind"}
        item = {**body, "kind": "div", "div_kind": div_kind}
        canonical = "div"
    else:
        alias = _NODE_KIND_ALIASES.get(kind)
        if alias is not None:
            item = {**item, "kind": alias}
            canonical = alias
        else:
            canonical = str(kind) if kind is not None else ""
    if canonical in _SOURCE_REF_KINDS and "source" in item:
        item = {
            **item,
            "source": normalize_source_endpoint_input(
                item["source"], ctx=f"{canonical}.source"
            ),
        }
    elif canonical == "mux" and isinstance(item.get("source"), dict):
        item = {
            **item,
            "source": {
                str(key): normalize_source_endpoint_input(
                    value, ctx="mux.source"
                )
                for key, value in item["source"].items()
            },
        }
    return item


def _coerce_required_freq(value: Any) -> int:
    if value is None or value == "":
        raise ValueError("须填写 freq")
    return int(value)


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def parse_source_endpoint(raw: Any, *, ctx: str) -> tuple[str, str]:
    text = normalize_source_endpoint_input(raw, ctx=ctx)
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
        description="RTL 层次路径，按 `.` 分隔；pll_mini 仅接受，不参与求解与生成。",
    )


class GateNode(NodeBase):
    kind: Literal["gate"] = "gate"
    source: str = Field(..., min_length=1, description="前级引用。")
    open: Optional[int] = Field(
        None,
        ge=0,
        le=1,
        description="门控开关，0 关闭、1 打开；省略表示由求解器决定；"
        "已填写时功能固定，不写 reg。",
    )
    reg: str = Field(
        "",
        description="门控寄存器模型点分路径；空则生成时跳过写寄存器；"
        "open 已填写时也应为空。",
    )

    @model_validator(mode="after")
    def _validate_gate_reg(self, info: ValidationInfo) -> GateNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="gate"
        )
        if self.open is not None and self.reg:
            raise ValueError(
                f"gate 节点 {_validation_node_name(self, info)!r} "
                f"已指定 open 时 reg 应为空"
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
        description="分频比；div_r 必填固定值，大于 0，不受可配置 div 的 64 上限；"
        "其余 div 省略表示由求解器决定；已填写时功能固定，不写 regs，且不大于 64。",
    )
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键由 div_kind 决定：div/div_n 为 rst、load、div；"
        "dto/dto_n 为 rst、load、bypass、step；"
        "cpu_gate 为 rst、div；"
        "div_r 不可配置寄存器，应为空；ratio 已填写时也应为空。",
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

    @model_validator(mode="after")
    def _validate_div_regs(self, info: ValidationInfo) -> DivNode:
        if self.div_kind == "div_r":
            if self.ratio is None:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 div_r 时须填写 ratio"
                )
        elif self.ratio is not None:
            if self.div_kind == "cpu_gate":
                if self.ratio not in _CPU_GATE_RATIOS:
                    allowed = "、".join(str(r) for r in sorted(_CPU_GATE_RATIOS))
                    raise ValueError(
                        f"div 节点 {_validation_node_name(self, info)!r} "
                        f"div_kind 为 cpu_gate 时 ratio 只能是 {allowed}，"
                        f"得到 {self.ratio}"
                    )
            elif self.ratio > 64:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"div_kind 为 {self.div_kind!r} 时 ratio 应不大于 64，"
                    f"得到 {self.ratio}"
                )
            if self.regs:
                raise ValueError(
                    f"div 节点 {_validation_node_name(self, info)!r} "
                    f"已指定 ratio 时 regs 应为空"
                )
        validate_regs_exact(
            self.regs,
            div_reg_keys_for_kind(self.div_kind),
            node_name=_validation_node_name(self, info),
            kind=f"div({self.div_kind})",
        )
        return self


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    inv_kind: InvKind = Field(
        "inv",
        description="反相器型号：inv、inv_mux、inv_cell，大小写不限。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")
    reg: str = Field(
        "",
        description="反相/直通控制寄存器模型路径；pll_mini 仅接受，不写寄存器。",
    )

    @field_validator("inv_kind", mode="before")
    @classmethod
    def _normalize_inv_kind(cls, value: object) -> str:
        return normalize_inv_kind(value)


class ClockSourceNode(NodeBase):
    kind: Literal["source"] = "source"
    source_kind: SourceKind = Field(
        "source",
        description="输入源型号：source、pad、vdd、gnd，大小写不限。",
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
                "source_kind 为 source、pad 时须填写大于 0 的 freq"
            )
        return self


class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    freq: Optional[int] = Field(
        default=None,
        description="目标输出频率，单位 Hz；inno 可省略，由各路下游 clk 约束。",
    )
    source: str = Field(..., min_length=1, description="参考时钟前级引用。")
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw、inno。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键须与 pll_kind 允许集合完全一致。",
    )

    @model_validator(mode="after")
    def _validate_pll_freq(self) -> PllNode:
        if self.pll_kind != "inno":
            if self.freq is None or self.freq < 1:
                raise ValueError(
                    f"pll 节点 {self.name!r} pll_kind 为 {self.pll_kind!r} 时"
                    f"须填写大于 0 的 freq"
                )
        elif self.freq is not None and self.freq < 1:
            raise ValueError(
                f"pll 节点 {self.name!r} freq 若填写须大于 0"
            )
        return self

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_pll_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_pll_kind(cls, value: object) -> str:
        return normalize_pll_kind(value)

    @computed_field(  # type: ignore[prop-decorator]
        description="inno 为 0、1 两路输出名；其它 pll 为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        if self.pll_kind == "inno":
            return list(INNO_PLL_OUTPUT_GROUPS)
        return []

    @model_validator(mode="after")
    def _validate_pll_regs(self, info: ValidationInfo) -> PllNode:
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
        description="配置型号，任意非空字符串；仅作记录，频率行为相同。",
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
        "正数同时指定频率与使能；负数仅不约束 resolved_freq。",
    )
    source: str = Field(..., min_length=1, description="前级引用。")
    always_active: bool = Field(
        default=False,
        description="为真时该时钟节点全程保持有效。",
    )

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_optional_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

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
        description="多路输入：键为输入标签，值为前级引用。",
    )
    sel: Optional[int] = Field(
        None,
        ge=0,
        description="mux 选择值；省略表示由求解器决定；已填写时功能固定，不写 reg。",
    )
    reg: str = Field(
        "",
        description="mux 选择寄存器模型点分路径；空则生成时跳过写寄存器；"
        "sel 已填写时也应为空。",
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="mux 的 source 键最大值；YAML 不可传入。",
    )
    @property
    def mux_max_sel(self) -> int:
        if not self.source:
            return 0
        return max(int(k) for k in self.source.keys())

    @model_validator(mode="after")
    def _validate_mux(self, info: ValidationInfo) -> MuxNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="mux"
        )
        if self.sel is not None:
            if self.reg:
                raise ValueError(
                    f"mux 节点 {_validation_node_name(self, info)!r} "
                    f"已指定 sel 时 reg 应为空"
                )
            if self.sel > self.mux_max_sel:
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

_NODE_KINDS_TEXT = "gate、div、inv、source、pll、cell、clk、mux"


def _node_kind_diagnosis(item: Any) -> str:
    if not isinstance(item, dict):
        return f"应为对象，得到 {type(item).__name__}"
    kind = item.get("kind")
    if kind is None:
        return "缺少 kind 字段"
    return (
        f"kind 为 {kind!r} 无法识别，应为 {_NODE_KINDS_TEXT} 之一；"
        f"分频旧写法可用 div、div_n、dto、dto_n、cpu_gate、div_r 作为 kind"
    )


def _format_node_validation_error(
    node_key: str,
    item: Any,
    exc: ValidationError,
) -> str:
    errors = exc.errors()
    if len(errors) == 1 and errors[0].get("type") in (
        "union_tag_not_found",
        "union_tag_invalid",
    ):
        return f"nodes[{node_key!r}] {_node_kind_diagnosis(item)}"
    parts: list[str] = []
    for err in errors:
        loc = err.get("loc", ())
        loc_text = ".".join(str(part) for part in loc)
        msg = str(err.get("msg", ""))
        parts.append(f"{loc_text}: {msg}" if loc_text else msg)
    return f"nodes[{node_key!r}] " + "；".join(parts)


def _validate_node_at_key(node_key: str, item: Any) -> Node:
    try:
        return _node_adapter.validate_python(item, context={"node_name": node_key})
    except ValidationError as exc:
        raise ValueError(
            _format_node_validation_error(node_key, item, exc)
        ) from exc


def _validation_node_name(node: NodeBase, info: ValidationInfo) -> str:
    key = (info.context or {}).get("node_name")
    if isinstance(key, str) and key:
        return key
    if node._name:
        return node._name
    raise ValueError("节点须在 Tree.nodes 字典键上下文内校验")


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="时钟树名。")
    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键即节点名；节点体内勿填 name。",
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
            node = _validate_node_at_key(key, item)
            object.__setattr__(node, "_name", key)
            built[key] = node
        return built

    @model_validator(mode="after")
    def _validate_name(self) -> Tree:
        if not _SV_ID.match(self.name):
            raise ValueError(
                f"tree.name {self.name!r} 须为合法 SystemVerilog 名字"
            )
        return self

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
    """校验 source、mux.source 等前级引用与输出名。

    Raises:
        ValueError: 引用节点不存在或输出名非法时。
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

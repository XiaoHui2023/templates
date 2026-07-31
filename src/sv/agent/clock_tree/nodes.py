from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Dict, List, Literal, Optional, Union

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
from pydantic.functional_validators import BeforeValidator

from reg_paths import (
    DIV_KIND_TO_SV,
    INV_KIND_TO_SV,
    INNO_PLL_OUTPUT_GROUPS,
    PLL_KIND_TO_SV,
    SOURCE_KIND_TO_SV,
    div_reg_keys_for_kind,
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
from schema_error import ERR

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SOURCE_ENDPOINT = re.compile(
    r"^(?P<device>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<group>[^\]]+)\])?$"
)
_GROUP_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_NODE_KIND_ALIASES: dict[str, str] = {
    "clock": "clk",
}

_LEGACY_DIV_KINDS = frozenset({"div", "dto", "div_r"})

_FREQ_HZ_U32_MAX = 2**32 - 1

PllKind = Literal["tci", "sc", "dw", "inno"]
DivKind = Literal["div", "dto", "div_r"]
InvKind = Literal["inv", "inv_mux", "inv_cell"]
SourceKind = Literal["source", "pad"]
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
        raise ValueError(ERR.missing_field("freq"))
    return int(value)


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _coerce_required_freq_or_map(value: Any) -> Union[int, Dict[str, int]]:
    if value is None or value == "":
        raise ValueError(ERR.missing_field("freq"))
    if isinstance(value, dict):
        return {str(key): int(freq) for key, freq in value.items()}
    return int(value)


def _coerce_optional_source(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    text = str(value).strip()
    return text if text else None


OptionalUpstreamSource = Annotated[
    Optional[str],
    BeforeValidator(_coerce_optional_source),
]


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


@dataclass(frozen=True)
class SvPortSlot:
    """展开到 SV 的单个 RTL 端口。"""

    node_key: str
    group_id: str
    access: str
    role: str
    port_key: str
    path: str
    instance_name: str
    force_macro: str
    path_macro: str


def _validate_sv_dot_path(value: Optional[str], *, field: str) -> Optional[str]:
    if value is None:
        return value
    for seg in value.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(
                f"{ERR.field(field)} 段 {seg!r} 须为合法 SystemVerilog 名字，"
                f"完整 {ERR.field(field)}: {value!r}"
            )
    return value


def _validate_path_map(
    value: Optional[Dict[str, str]],
    *,
    field: str,
) -> Optional[Dict[str, str]]:
    if value is None:
        return value
    for key, path in value.items():
        if not _GROUP_KEY_RE.match(str(key)):
            raise ValueError(
                f"{ERR.field(field)} 键 {key!r} 须为合法 SystemVerilog 名字"
            )
        _validate_sv_dot_path(path, field=field)
    return {str(key): path for key, path in value.items()}


def _reject_fields(data: Any, *, kind: str, fields: Dict[str, str]) -> Any:
    if not isinstance(data, dict):
        return data
    for field, replacement in fields.items():
        if field in data:
            raise ValueError(ERR.unsupported_field(kind, field, replacement))
    return data


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

    present: bool = Field(
        True,
        description="为假时该节点不生成 SV 实例、不进入 tree；其它节点引用它时不连接。",
    )

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
        if self.source is None:
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

class GateNode(NodeBase):
    kind: Literal["gate"] = "gate"
    in_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输入端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输出端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    source: OptionalUpstreamSource = Field(
        default=None,
        description="前级引用；省略或空表示无前级。",
    )
    open: Optional[int] = Field(
        None,
        ge=0,
        le=1,
        description="门控开关；0 关闭、1 打开；省略表示随机化。",
    )
    reg: str = Field(
        "",
        description="寄存器模型路径。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_path_plural(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="gate",
            fields={"in_paths": "in_path", "out_paths": "out_path"},
        )

    @field_validator("in_path", "out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

    @computed_field(  # type: ignore[prop-decorator]
        description="tree 构造写入 open；省略时为 -1；YAML 不可传入。",
    )
    @property
    def gate_init_open(self) -> int:
        return -1 if self.open is None else self.open

    @computed_field(  # type: ignore[prop-decorator]
        description="open 非 gate::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def gate_tree_emit_unfix_open(self) -> bool:
        return self.open is not None

    @model_validator(mode="after")
    def _validate_gate_reg(self, info: ValidationInfo) -> GateNode:
        validate_optional_reg(
            self.reg, node_name=_validation_node_name(self, info), kind="gate"
        )
        return self


class DivNode(NodeBase):
    kind: Literal["div"] = "div"
    in_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输入端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输出端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    div_kind: DivKind = Field(
        "div",
        description="分频器型号：div、dto、div_r，大小写不限。",
    )
    source: OptionalUpstreamSource = Field(
        default=None,
        description="前级引用；省略或空表示无前级。",
    )
    ratio: Optional[int] = Field(
        None,
        ge=1,
        description="分频比；div_r 必填固定值，大于 0；"
        "其余 div 省略表示随机化。",
    )
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="非空时键由 div_kind 决定：div 为 rst、load、div；"
        "dto 为 rst、load、bypass、step；"
        "div_r 不可配置寄存器，须为空。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_path_plural(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="div",
            fields={"in_paths": "in_path", "out_paths": "out_path"},
        )

    @field_validator("in_path", "out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

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
        node_name = _validation_node_name(self, info)
        if self.div_kind == "div_r":
            if self.ratio is None:
                raise ValueError(
                    f"{ERR.node('div', node_name)} "
                    f"{ERR.field('div_kind')} 为 'div_r' 时须填写 {ERR.field('ratio')}"
                )
        validate_regs_exact(
            self.regs,
            div_reg_keys_for_kind(self.div_kind),
            node_name=node_name,
            kind=f"div({self.div_kind})",
        )
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="tree 构造写入 ratio；省略时为 -1；YAML 不可传入。",
    )
    @property
    def div_init_ratio(self) -> int:
        return -1 if self.ratio is None else self.ratio

    @computed_field(  # type: ignore[prop-decorator]
        description="ratio 非 div_base::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def div_tree_emit_unfix_ratio(self) -> bool:
        return self.ratio is not None


class InvNode(NodeBase):
    kind: Literal["inv"] = "inv"
    in_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输入端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输出端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
    inv_kind: InvKind = Field(
        "inv",
        description="反相器型号：inv、inv_mux、inv_cell，大小写不限。",
    )
    source: OptionalUpstreamSource = Field(
        default=None,
        description="前级引用；省略或空表示无前级。",
    )
    reg: str = Field(
        "",
        description="反相/直通控制寄存器模型路径。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_path_plural(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="inv",
            fields={"in_paths": "in_path", "out_paths": "out_path"},
        )

    @field_validator("in_path", "out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

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
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输出端 RTL 层次路径；用于 route 端口检查，可省略。",
    )
    source_kind: SourceKind = Field(
        "source",
        description="输入源型号：source、pad，大小写不限。",
    )
    freq: Optional[int] = Field(
        None,
        description="典型频率，单位 Hz。",
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> str:
        return normalize_source_kind(value)

    @model_validator(mode="before")
    @classmethod
    def _reject_wrong_rtl_paths(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="source",
            fields={"in_path": "out_path", "in_paths": "out_path", "out_paths": "out_path"},
        )

    @field_validator("out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

    @computed_field(  # type: ignore[prop-decorator]
        description="由 source_kind 映射的 SV 模型类名片段；YAML 与 model_validate 不可传入。",
    )
    @property
    def sv_source_class(self) -> str:
        return SOURCE_KIND_TO_SV[self.source_kind]

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

class PllNode(NodeBase):
    kind: Literal["pll"] = "pll"
    in_path: Optional[str] = Field(
        None,
        min_length=1,
        description="参考输入端 RTL 层次路径；用于 route 端口检查，可省略。",
    )
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="单输出 PLL 的输出端 RTL 层次路径；用于 route 端口检查，可省略。",
    )
    out_paths: Optional[Dict[str, str]] = Field(
        None,
        description="多输出 PLL 的输出端 RTL 层次路径；键为输出名，可省略。",
    )
    freq: Union[int, Dict[str, int]] = Field(
        ...,
        description="典型频率，单位 Hz；pll_kind 为 inno 时可写各输出端口频率 dict。",
    )
    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_freq(cls, value: Any) -> Any:
        return _coerce_required_freq_or_map(value)
    source: OptionalUpstreamSource = Field(
        default=None,
        description="参考时钟前级引用；省略或空表示无前级。",
    )
    pll_kind: PllKind = Field(..., description="PLL 型号：tci、sc、dw、inno，大小写不限。")
    regs: Dict[str, str] = Field(
        default_factory=dict,
        description="逻辑名到寄存器模型路径；非空时键须与 pll_kind 允许集合一致。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_wrong_rtl_paths(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="pll",
            fields={"in_paths": "in_path"},
        )

    @field_validator("in_path", "out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

    @field_validator("out_paths")
    @classmethod
    def _validate_rtl_path_map(
            cls,
            value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        return _validate_path_map(value, field="out_paths")

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
        description="inno 为 0、1 两路输出名；其它 pll 为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        if self.pll_kind == "inno":
            return list(INNO_PLL_OUTPUT_GROUPS)
        return []

    @model_validator(mode="after")
    def _validate_pll_freq(self, info: ValidationInfo) -> PllNode:
        node_name = _validation_node_name(self, info)
        if self.output_groups:
            if self.out_path is not None:
                raise ValueError(
                    f"{ERR.node('pll', node_name)} 多输出 PLL 请使用 "
                    f"{ERR.field('out_paths')}，不要使用 {ERR.field('out_path')}"
                )
            if self.out_paths:
                expected_paths = set(self.output_groups)
                actual_paths = set(self.out_paths)
                extra = sorted(actual_paths - expected_paths)
                if extra:
                    raise ValueError(
                        f"{ERR.node('pll', node_name)} {ERR.field('out_paths')} "
                        f"包含非法输出 {extra}；允许 {sorted(expected_paths)}"
                    )
        else:
            if self.out_paths is not None:
                raise ValueError(
                    f"{ERR.node('pll', node_name)} 单输出 PLL 请使用 "
                    f"{ERR.field('out_path')}，不要使用 {ERR.field('out_paths')}"
                )
        if isinstance(self.freq, dict):
            if self.pll_kind != "inno":
                raise ValueError(
                    f"{ERR.node('pll', node_name)} {ERR.field('freq')} 为 dict 时 "
                    f"{ERR.field('pll_kind')} 必须为 'inno'"
                )
            expected = set(self.output_groups)
            actual = set(self.freq)
            if actual != expected:
                raise ValueError(
                    f"{ERR.node('pll', node_name)} {ERR.field('pll_kind')} 为 'inno' 时 "
                    f"{ERR.field('freq')} dict 键必须为 {sorted(expected)!r}"
                )
            for group, freq in self.freq.items():
                if freq < 1 or freq > _FREQ_HZ_U32_MAX:
                    raise ValueError(
                        f"{ERR.node('pll', node_name)} {ERR.field('freq')}[{group!r}] "
                        f"必须在 1～{_FREQ_HZ_U32_MAX}"
                    )
        elif self.freq < 1 or self.freq > _FREQ_HZ_U32_MAX:
            raise ValueError(
                f"{ERR.node('pll', node_name)} {ERR.field('freq')} "
                f"必须在 1～{_FREQ_HZ_U32_MAX}"
            )
        return self

    @model_validator(mode="after")
    def _validate_pll_regs(self, info: ValidationInfo) -> PllNode:
        validate_pll_regs_exact(
            self.regs,
            self.pll_kind,
            node_name=_validation_node_name(self, info),
            output_groups=self.output_groups,
        )
        return self

    def freq_for_group(self, group: str) -> int:
        if isinstance(self.freq, dict):
            return self.freq[group]
        return self.freq

class CellNode(NodeBase):
    kind: Literal["cell"] = "cell"
    path: Optional[str] = Field(
        None,
        min_length=1,
        description="RTL 层次路径，按 `.` 分隔；present 为真时必填。",
    )
    cell_kind: str = Field(
        "cell",
        min_length=1,
        description="配置型号，任意非空字符串；仅作记录，仿真行为相同。",
    )
    freq: Optional[int] = Field(
        default=None,
        description="典型频率，单位 Hz；省略表示不指定频率。",
    )
    active: Optional[bool] = Field(
        default=None,
        description="期望运行态是否有时钟；省略表示不指定活动状态。",
    )
    source: OptionalUpstreamSource = Field(
        default=None,
        description="前级引用；省略或空表示无前级。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_disable(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "disable" in data:
            raise ValueError(ERR.unsupported_field("cell", "disable", "active: false"))
        data = _reject_fields(
            data,
            kind="cell",
            fields={
                "in_path": "path",
                "in_paths": "path",
                "out_path": "path",
                "out_paths": "path",
            },
        )
        return data

    @field_validator("cell_kind", mode="before")
    @classmethod
    def _normalize_cell_kind(cls, value: object) -> str:
        return normalize_cell_kind(value)

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_optional_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: Optional[str]) -> Optional[str]:
        return _validate_sv_dot_path(value, field="path")

    @model_validator(mode="after")
    def _validate_cell_path(self, info: ValidationInfo) -> CellNode:
        node_name = _validation_node_name(self, info)
        if self.present and not self.path:
            raise ValueError(f"{ERR.node('cell', node_name)} {ERR.field('path')} 必须填写")
        if self.freq is not None and self.freq == 0:
            raise ValueError(
                f"{ERR.node('cell', node_name)} {ERR.field('freq')} 为 0 非法；"
                f"正频率应大于等于 1，不约束请省略或填负数"
            )
        if self.freq is not None and self.freq > _FREQ_HZ_U32_MAX:
            raise ValueError(
                f"{ERR.node('cell', node_name)} {ERR.field('freq')} {self.freq} "
                f"超过 32 位无符号整数上限 {_FREQ_HZ_U32_MAX}"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cell_init_frequence(self) -> int:
        return -1 if self.freq is None else self.freq

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cell_init_enabled(self) -> int:
        if self.active is None:
            return -1
        return 1 if self.active else 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cell_tree_emit_frequence(self) -> bool:
        if self.active is False:
            return False
        return self.freq is not None and self.freq != -1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cell_tree_emit_enabled(self) -> bool:
        return self.active is not None


class ClkNode(NodeBase):
    kind: Literal["clk"] = "clk"
    path: Optional[str] = Field(
        None,
        min_length=1,
        description="RTL 层次路径，按 `.` 分隔；present 为真时必填。",
    )
    freq: Optional[int] = Field(
        default=None,
        description="典型频率，单位 Hz；省略表示不指定频率；"
        "正数锁定 frequence；负数仅不约束 _resolved_freq。",
    )
    active: Optional[bool] = Field(
        default=None,
        description="期望运行态是否有时钟；省略表示不主动控制，为假时仍生成并检查 inactive。",
    )
    source: OptionalUpstreamSource = Field(
        default=None,
        description="前级引用；省略或空表示无前级。",
    )
    stable: bool = Field(
        default=False,
        description="为真时表示锚定时钟：结构探测与低功耗下不得关断或改频；"
        "应配合正整数 freq，tree 锁定 frequence 并将 enabled 置 1。",
    )

    check_duty: bool = Field(
        default=True,
        description="为真时 check_measure 检查占空比；为假时只检查频率。",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_disable(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "disable" in data:
            raise ValueError(ERR.unsupported_field("clk", "disable", "active: false"))
        if "volatile" in data:
            raise ValueError(ERR.unsupported_field("clk", "volatile", "check_duty: false"))
        data = _reject_fields(
            data,
            kind="clk",
            fields={
                "in_path": "path",
                "in_paths": "path",
                "out_path": "path",
                "out_paths": "path",
            },
        )
        return data

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_optional_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: Optional[str]) -> Optional[str]:
        return _validate_sv_dot_path(value, field="path")

    @computed_field(  # type: ignore[prop-decorator]
        description="tree 构造写入 frequence；省略 freq 时为 -1；YAML 不可传入。",
    )
    @property
    def clk_init_frequence(self) -> int:
        return -1 if self.freq is None else self.freq

    @computed_field(  # type: ignore[prop-decorator]
        description="tree 构造写入 enabled；未显式配置时为 -1；YAML 不可传入。",
    )
    @property
    def clk_init_enabled(self) -> int:
        if self.active is False:
            return 0
        if self.active is True or self.stable or (
            self.freq is not None and self.freq > 0
        ):
            return 1
        return -1

    @computed_field(  # type: ignore[prop-decorator]
        description="frequence 非 clk::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def clk_tree_emit_frequence(self) -> bool:
        return self.freq is not None and self.freq != -1

    @computed_field(  # type: ignore[prop-decorator]
        description="active、freq 或 stable 显式要求初始 enabled 时为真；YAML 不可传入。",
    )
    @property
    def clk_tree_emit_enabled(self) -> bool:
        return self.active is not None or self.stable or (
            self.freq is not None and self.freq > 0
        )

    @model_validator(mode="after")
    def _validate_clk_freq(self, info: ValidationInfo) -> ClkNode:
        node_name = _validation_node_name(self, info)
        if self.present and not self.path:
            raise ValueError(f"{ERR.node('clk', node_name)} {ERR.field('path')} 必须填写")
        if self.freq is not None and self.freq == 0:
            raise ValueError(
                f"{ERR.node('clk', node_name)} {ERR.field('freq')} 为 0 非法；"
                f"正频率应大于等于 1，不约束请省略或填负数"
            )
        if self.freq is not None and self.freq > _FREQ_HZ_U32_MAX:
            raise ValueError(
                f"{ERR.node('clk', node_name)} {ERR.field('freq')} {self.freq} "
                f"超过 32 位无符号整数上限 {_FREQ_HZ_U32_MAX}"
            )
        if self.stable and (self.freq is None or self.freq <= 0):
            raise ValueError(
                f"{ERR.node('clk', node_name)} {ERR.field('stable')} 为真时 "
                f"{ERR.field('freq')} 应为正整数"
            )
        if self.active is False and self.stable:
            raise ValueError(
                f"{ERR.node('clk', node_name)} {ERR.field('active')} 为假时"
                f"不可同时 {ERR.field('stable')}"
            )
        return self


class MuxNode(NodeBase):
    kind: Literal["mux"] = "mux"
    in_paths: Optional[Dict[str, str]] = Field(
        None,
        description="输入端 RTL 层次路径；键对应 source 选择值，用于 route/flip 端口检查，可省略。",
    )
    out_path: Optional[str] = Field(
        None,
        min_length=1,
        description="输出端 RTL 层次路径；用于 route/flip 端口检查，可省略。",
    )
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

    @model_validator(mode="before")
    @classmethod
    def _reject_wrong_rtl_paths(cls, data: Any) -> Any:
        return _reject_fields(
            data,
            kind="mux",
            fields={"in_path": "in_paths", "out_paths": "out_path"},
        )

    @field_validator("out_path")
    @classmethod
    def _validate_rtl_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return _validate_sv_dot_path(value, field=info.field_name or "path")

    @field_validator("in_paths")
    @classmethod
    def _validate_rtl_path_map(
            cls,
            value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        return _validate_path_map(value, field="in_paths")

    @computed_field(  # type: ignore[prop-decorator]
        description="tree 构造写入 sel；省略时为 -1；YAML 不可传入。",
    )
    @property
    def mux_init_sel(self) -> int:
        return -1 if self.sel is None else self.sel

    @computed_field(  # type: ignore[prop-decorator]
        description="sel 非 mux::new 默认 -1 时为真；YAML 不可传入。",
    )
    @property
    def mux_tree_emit_unfix_sel(self) -> bool:
        return self.sel is not None

    @model_validator(mode="after")
    def _validate_mux(self, info: ValidationInfo) -> MuxNode:
        node_name = _validation_node_name(self, info)
        validate_optional_reg(
            self.reg, node_name=node_name, kind="mux"
        )
        if self.in_paths:
            source_keys = set(str(key) for key in self.source.keys())
            path_keys = set(str(key) for key in self.in_paths.keys())
            extra = sorted(path_keys - source_keys)
            if extra:
                raise ValueError(
                    f"{ERR.node('mux', node_name)} {ERR.field('in_paths')} "
                    f"包含未在 {ERR.field('source')} 中声明的输入 {extra}"
                )
        if self.sel is not None and self.sel > self.mux_max_sel:
            raise ValueError(
                f"{ERR.node('mux', node_name)} "
                f"{ERR.field('sel')} 为 {self.sel} 超出 "
                f"{ERR.field('source')} 键范围 0～{self.mux_max_sel}"
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
        return f"缺少 {ERR.field('kind')} 字段"
    return (
        f"{ERR.field('kind')} 为 {kind!r} 无法识别，应为 {_NODE_KINDS_TEXT} 之一；"
        f"分频旧写法可用 div、dto、div_r 作为 {ERR.field('kind')}"
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
    raise ValueError(f"节点须在 {ERR.field('Tree.nodes')} 字典键上下文内校验")


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _cache: Dict[str, Any] = PrivateAttr(default_factory=dict)

    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键为节点名；值不可为 null。",
    )

    def _cached(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

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
                if item is None:
                    raise ValueError(f"{ERR.field('nodes')} 列表项不可为 null")
                if not isinstance(item, dict):
                    as_dict[str(item)] = item
                    continue
                item = _normalize_node_item(item)
                node_name = item.get("name")
                if not node_name:
                    raise ValueError(
                        f"{ERR.field('nodes')} 为列表时每项须含 {ERR.field('name')}；"
                        f"请改用 dict，以键为 {ERR.field('name')}"
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
                    f"{ERR.field('nodes')} 键 {key!r} 须为合法 SystemVerilog 名字"
                )
            if item is None:
                raise ValueError(f"{ERR.nodes_key(key)} 不可为 null")
            if isinstance(item, dict):
                item = _normalize_node_item(item)
                if "name" in item:
                    raise ValueError(
                        f"{ERR.nodes_key(key)} 体内不可含 {ERR.field('name')}，"
                        f"以字典键 {key!r} 为准"
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
            if item is None:
                raise ValueError(f"{ERR.nodes_key(key)} 不可为 null")
            if isinstance(item, NodeBase):
                object.__setattr__(item, "_name", key)
                built[key] = item
                continue
            node = _validate_node_at_key(key, item)
            object.__setattr__(node, "_name", key)
            built[key] = node
        return built

    @computed_field(  # type: ignore[prop-decorator]
        description="nodes 值的有序列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def nodes_ordered(self) -> List[Node]:
        return self._cached(
            "nodes_ordered",
            lambda: [node for node in self.nodes.values() if node.present],
        )

    @computed_field(  # type: ignore[prop-decorator]
        description="展开到 SV 的节点实例槽位；多路输出器件按路展开；YAML 不可传入。",
    )
    @property
    def sv_slots(self) -> List[SvNodeSlot]:
        return self._cached("sv_slots", self._sv_slots)

    def _sv_slots(self) -> List[SvNodeSlot]:
        slots: List[SvNodeSlot] = []
        for key, node in self.nodes.items():
            if not node.present:
                continue
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
        description="RTL 端口槽位；用于 interface、tree_interface 与 connect；YAML 不可传入。",
    )
    @property
    def port_slots(self) -> List[SvPortSlot]:
        return self._cached("port_slots", self._port_slots)

    def _port_slots(self) -> List[SvPortSlot]:
        slots: List[SvPortSlot] = []

        def add_slot(
                *,
                node_key: str,
                group_id: str,
                access: str,
                role: str,
                port_key: str,
                path: Optional[str]) -> None:
            if not path:
                return
            suffix_parts = [node_key]
            if group_id:
                suffix_parts.append(group_id)
            suffix_parts.append(role)
            if port_key != "default":
                suffix_parts.append(port_key)
            instance_name = "_".join(suffix_parts) + "_if"
            force_macro = (
                f"{node_key}_{group_id + '_' if group_id else ''}"
                f"{role}_{port_key}"
            ).upper()
            macro_parts = [node_key]
            if group_id:
                macro_parts.append(group_id)
            macro_parts.append(role)
            if port_key != "default":
                macro_parts.append(port_key)
            slots.append(
                SvPortSlot(
                    node_key=node_key,
                    group_id=group_id,
                    access=access,
                    role=role,
                    port_key=port_key,
                    path=path,
                    instance_name=instance_name,
                    force_macro=force_macro,
                    path_macro="_".join(macro_parts).upper(),
                )
            )

        for slot in self.sv_slots:
            node = self.nodes[slot.node_key]
            if node.kind in ("clk", "cell"):
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="in",
                    port_key="default",
                    path=getattr(node, "path", None),
                )
            elif node.kind == "source":
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="out",
                    port_key="default",
                    path=node.out_path,
                )
            elif node.kind == "mux":
                if node.in_paths:
                    for key, path in sorted(node.in_paths.items()):
                        add_slot(
                            node_key=slot.node_key,
                            group_id=slot.group_id,
                            access=slot.access,
                            role="in",
                            port_key=str(key),
                            path=path,
                        )
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="out",
                    port_key="default",
                    path=node.out_path,
                )
            elif node.kind == "pll":
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="in",
                    port_key="default",
                    path=node.in_path,
                )
                if node.output_groups:
                    path = (node.out_paths or {}).get(slot.group_id)
                    add_slot(
                        node_key=slot.node_key,
                        group_id=slot.group_id,
                        access=slot.access,
                        role="out",
                        port_key="default",
                        path=path,
                    )
                else:
                    add_slot(
                        node_key=slot.node_key,
                        group_id=slot.group_id,
                        access=slot.access,
                        role="out",
                        port_key="default",
                        path=node.out_path,
                    )
            else:
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="in",
                    port_key="default",
                    path=getattr(node, "in_path", None),
                )
                add_slot(
                    node_key=slot.node_key,
                    group_id=slot.group_id,
                    access=slot.access,
                    role="out",
                    port_key="default",
                    path=getattr(node, "out_path", None),
                )
        return slots

    @computed_field(  # type: ignore[prop-decorator]
        description="RTL 端口槽位；用于测量 interface 与 tree_interface；YAML 不可传入。",
    )
    @property
    def connectable_slots(self) -> List[SvPortSlot]:
        return self._cached(
            "connectable_slots",
            lambda: self.port_slots,
        )

    def source_sv_access(self, ref: SourceRef) -> str:
        peer = self.nodes[ref.name]
        groups = node_output_groups(peer)
        return sv_node_access(ref.name, ref.out_group, groups)

    @computed_field(  # type: ignore[prop-decorator]
        description="由各节点 source 反查；键为器件名，值为以其为前级的子节点名列表；YAML 不可传入。",
    )
    @property
    def children_by_node(self) -> Dict[str, List[str]]:
        return self._cached(
            "children_by_node",
            lambda: build_children_map(self.nodes),
        )

    @model_validator(mode="after")
    def _validate_nodes_graph(self) -> Tree:
        return self


def upstream_peer_names(node: Node) -> List[str]:
    if node.kind == "mux":
        return [
            parse_source_endpoint(peer, ctx="mux.source")[0]
            for peer in node.source.values()
        ]
    if node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
        if node.source is None:
            return []
        device, _out_group = parse_source_endpoint(node.source, ctx="source")
        return [device]
    return []


def build_children_map(nodes: Dict[str, Node]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {
        key: [] for key, node in nodes.items() if node.present
    }
    for child_name, node in nodes.items():
        if not node.present:
            continue
        for parent_name in upstream_peer_names(node):
            parent = nodes.get(parent_name)
            if parent is not None and parent.present:
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
        if not node.present:
            continue
        if node.name != key:
            raise ValueError(
                f"{ERR.nodes_key(key)} 的 {ERR.field('name')} 字段 {node.name!r} "
                f"须与字典键一致"
            )
        if node.kind == "source" and (
            node.freq is None or node.freq < 1 or node.freq > _FREQ_HZ_U32_MAX
        ):
            raise ValueError(
                f"{ERR.node('source', key)} 须填写 1～{_FREQ_HZ_U32_MAX} 的 "
                f"{ERR.field('freq')}"
            )
        if node.kind == "mux":
            for mux_key, peer in node.source.items():
                _validate_source_ref(
                    peer,
                    nodes,
                    ctx=f"节点 {key!r} {ERR.field('mux.source')}[{mux_key!r}]",
                )
        elif node.kind in ("gate", "div", "inv", "cell", "clk", "pll"):
            if node.source is not None:
                _validate_source_ref(
                    node.source,
                    nodes,
                    ctx=f"节点 {key!r} {ERR.field('source')}",
                )

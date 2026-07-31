from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    field_validator,
    model_validator,
)

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

from nodes import Node, Tree, validate_nodes_graph
from reg_paths import (
    DIV_KIND_TO_SV_ENUM,
    INV_KIND_TO_SV_ENUM,
    PLL_REG_KEYS,
    SOURCE_KIND_TO_SV_ENUM,
    RegBindingRow,
    any_node_path,
    any_reg_configured as tree_has_node_regs,
    collect_div_sv_classes,
    collect_inv_sv_classes,
    collect_pll_sv_classes,
    collect_source_sv_classes,
    iter_reg_bindings,
)
from schema_error import ERR

_MAX_FREQ_HZ = 5_000_000_000


def _format_freq_hz(freq_hz: int) -> str:
    for scale, unit in (
        (1_000_000_000, "GHz"),
        (1_000_000, "MHz"),
        (1_000, "kHz"),
        (1, "Hz"),
    ):
        if abs(freq_hz) >= scale or scale == 1:
            if scale == 1:
                return f"{freq_hz}Hz"
            return f"{freq_hz / scale:.3f}".rstrip("0").rstrip(".") + unit
    return f"{freq_hz}Hz"


def _clk_low_power_closed(node: Node) -> bool:
    return node.kind == "clk" and not node.stable and node.active is not False


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field(
        "clk_tree_",
        min_length=1,
        description="类型名前缀。",
    )
    class_regmodel: str = Field(
        "",
        description="寄存器模型类型名。",
    )
    direct_config: bool = Field(
        False,
        description="为真时额外生成轻量配置 filelist 和直接寄存器配置入口。",
    )
    min_freq_hz: int = Field(
        15000,
        ge=15000,
        description="测量接口与 check_measure 默认最低频率，单位 Hz；"
        "决定活动与稳定阶段超时时限及可测量频率下限。",
    )
    max_freq_hz: int = Field(
        _MAX_FREQ_HZ,
        ge=15000,
        le=_MAX_FREQ_HZ,
        description="clk 节点 randomize 后允许的最高频率，单位 Hz；"
        "活动时钟的 _resolved_freq 高于该值时 cst_clk 约束冲突。",
    )
    active_cycles: int = Field(
        1,
        ge=1,
        description="判定时钟有活动所需连续上升沿个数；"
        "未达个数且超过一个最低频率周期仍无边沿则 inactive。",
    )
    stable_cycles: int = Field(
        3,
        ge=2,
        description="活动确认后频率或占空比各自连续稳定所需周期数；中途失稳则重新计数。",
    )
    mux_switch_wait_cycles: int = Field(
        3,
        ge=1,
        description="config_reg 写 mux 选择前，按待切换 mux 最慢直接前级时钟等待的周期数。",
    )
    period_tolerance: float = Field(
        0.02,
        gt=0.0,
        lt=1.0,
        description="相邻周期相对偏差上限。",
    )
    div_freq_tolerance: float = Field(
        0.01,
        ge=0.0,
        lt=1.0,
        description="分频器解析频率相对容差。",
    )

    @property
    def div_freq_tolerance_den(self) -> int:
        if self.div_freq_tolerance <= 0.0:
            return 1
        exp = Decimal(str(self.div_freq_tolerance)).as_tuple().exponent
        if exp >= 0:
            return 1
        return 10 ** (-exp)

    @property
    def div_freq_tolerance_num(self) -> int:
        den = self.div_freq_tolerance_den
        return int(Decimal(str(self.div_freq_tolerance)) * den)

    duty_min: float = Field(
        48.0,
        ge=0.0,
        le=100.0,
        description="允许占空比下限，百分数；闭区间端点计入合格。",
    )
    duty_max: float = Field(
        67.0,
        ge=0.0,
        le=100.0,
        description="允许占空比上限，百分数；闭区间端点计入合格。",
    )
    duty_tolerance_pct: float = Field(
        0.05,
        ge=0.0,
        le=10.0,
        description="占空比允许范围在 duty_min、duty_max 之外的容差，百分数点；"
        "测量值在 [duty_min − duty_tolerance_pct, duty_max + duty_tolerance_pct] 内视为合格。",
    )
    pll_lock_timeout_us: int = Field(
        100,
        ge=1,
        description="PLL lock 等待上限，微秒。",
    )
    pll_sc_fbdiv_min: int = Field(
        16,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 下限。",
    )
    pll_sc_fbdiv_max: int = Field(
        84,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 上限。",
    )
    gate_reg_high_means_open: bool = Field(
        False,
        description="为真时门控寄存器位 1 表示打开；为假时 1 表示关闭。",
    )
    inv_reg_high_means_inverted: bool = Field(
        False,
        description="为真时 inv 寄存器位 1 表示反相输出；为假时 1 表示直通。",
    )
    div_reg_high_means_reset: bool = Field(
        False,
        description="为真时 div 的 rst 位 1 表示复位、0 不复位；"
        "为假时 0 表示复位、1 不复位。",
    )
    dto_reg_high_means_reset: bool = Field(
        False,
        description="为真时 dto 的 rst 位 1 表示复位、0 不复位；"
        "为假时 0 表示复位、1 不复位。",
    )
    should_reset_div: bool = Field(
        False,
        description="为真时每次 config_reg 配置 div 先拉 rst 到复位电平，"
        "再写 div 与 load、最后写 rst 为不复位；"
        "为假时首次只将 rst 写为不复位电平并写 div 与 load，"
        "此后仅更新 div 与 load，不经复位脉冲。",
    )
    should_reset_dto: bool = Field(
        False,
        description="为真时每次 config_reg 配置 dto 先拉 rst 到复位电平，"
        "再写 step、load 与 bypass、最后写 rst 为不复位；"
        "为假时首次只将 rst 写为不复位电平并写 step、load 与 bypass，"
        "此后仅更新 step、load 与 bypass，不经复位脉冲。",
    )

    @field_validator("duty_min", "duty_max", mode="before")
    @classmethod
    def _duty_as_percent(cls, v: object) -> object:
        if isinstance(v, (int, float)) and 0.0 < float(v) <= 1.0:
            return float(v) * 100.0
        return v

    @model_validator(mode="after")
    def _validate_freq_range(self) -> Settings:
        if self.min_freq_hz > self.max_freq_hz:
            raise ValueError(
                f"{ERR.field('min_freq_hz')} ({self.min_freq_hz}) 须不大于 "
                f"{ERR.field('max_freq_hz')} ({self.max_freq_hz})"
            )
        return self

    @model_validator(mode="after")
    def _validate_duty_range(self) -> Settings:
        if self.duty_min > self.duty_max:
            raise ValueError(
                f"{ERR.field('duty_min')} ({self.duty_min}) 须不大于 "
                f"{ERR.field('duty_max')} ({self.duty_max})"
            )
        return self

    @model_validator(mode="after")
    def _validate_pll_sc_fbdiv_range(self) -> Settings:
        if self.pll_sc_fbdiv_min > self.pll_sc_fbdiv_max:
            raise ValueError(
                f"{ERR.field('pll_sc_fbdiv_min')} ({self.pll_sc_fbdiv_min}) "
                f"须不大于 {ERR.field('pll_sc_fbdiv_max')} "
                f"({self.pll_sc_fbdiv_max})"
            )
        return self

    @field_validator("class_regmodel")
    @classmethod
    def _validate_class_regmodel(cls, value: str) -> str:
        if not value:
            return value
        if not _SV_TYPE.match(value):
            raise ValueError(
                f"{ERR.field('class_regmodel')} {value!r} 须为合法 SystemVerilog 类型名"
            )
        return value


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    _cache: Dict[str, Any] = PrivateAttr(default_factory=dict)

    nodes: Dict[str, Node] = Field(
        ...,
        min_length=1,
        description="节点表，键为节点名。",
    )
    settings: Settings = Field(
        default_factory=Settings,
        description="全局选项。",
    )

    def _cached(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    @field_validator("nodes", mode="before")
    @classmethod
    def _validate_nodes(cls, value: Any) -> Any:
        return Tree.model_validate({"nodes": value}).nodes

    @model_validator(mode="after")
    def _validate_nodes_for_mode(self) -> Models:
        validate_nodes_graph(self.nodes)
        if not tree_has_node_regs(self.tree):
            raise ValueError(
                f"至少须配置一个 {ERR.fields('reg', 'regs')}"
            )
        if not self.settings.class_regmodel:
            raise ValueError(
                f"任意节点配置了 {ERR.fields('reg', 'regs')} 时须在 "
                f"{ERR.field('settings')} 中填写 {ERR.field('class_regmodel')}"
            )
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="模板内部使用的节点树。",
    )
    @property
    def tree(self) -> Tree:
        return self._cached("tree", lambda: Tree(nodes=self.nodes))

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 PLL 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def pll_sv_classes(self) -> List[str]:
        return collect_pll_sv_classes(self.tree)

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 div 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def div_sv_classes(self) -> List[str]:
        return collect_div_sv_classes(self.tree)

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 inv 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def inv_sv_classes(self) -> List[str]:
        return collect_inv_sv_classes(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def div_kind_to_sv_enum(self) -> Dict[str, str]:
        return dict(DIV_KIND_TO_SV_ENUM)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inv_kind_to_sv_enum(self) -> Dict[str, str]:
        return dict(INV_KIND_TO_SV_ENUM)

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 source 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def source_sv_classes(self) -> List[str]:
        return collect_source_sv_classes(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_kind_to_sv_enum(self) -> Dict[str, str]:
        return dict(SOURCE_KIND_TO_SV_ENUM)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pll_reg_keys_by_kind(self) -> Dict[str, List[str]]:
        return {kind: sorted(keys) for kind, keys in PLL_REG_KEYS.items()}

    @computed_field(  # type: ignore[prop-decorator]
        description="存在可连接 RTL path 时为真；YAML 与 model_validate 不可传入。",
    )
    @property
    def enable_node_fix(self) -> bool:
        return any_node_path(self.tree)

    @computed_field(  # type: ignore[prop-decorator]
        description="enable_node_fix 与 any_node_path 均为真时生成 test_route；不可传入。",
    )
    @property
    def route_test_enabled(self) -> bool:
        return (
            self.enable_node_fix
            and self.any_node_path
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inno_pll_primary_group(self) -> str:
        return "0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_bindings(self) -> List[RegBindingRow]:
        return self._cached(
            "reg_bindings",
            lambda: iter_reg_bindings(self.tree),
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def any_node_path(self) -> bool:
        return any_node_path(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_clk_name(self) -> Optional[str]:
        return next(
            (node.name for node in self.tree.nodes_ordered if node.kind == "clk"),
            None,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_pll_access(self) -> Optional[str]:
        for node in self.tree.nodes_ordered:
            if node.kind != "pll":
                continue
            if node.output_groups:
                return f'{node.name}["{self.inno_pll_primary_group}"]'
            return node.name
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def configurable_clks(self) -> List[Dict[str, Any]]:
        return self._cached("configurable_clks", self._configurable_clks)

    def _configurable_clks(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for node in self.tree.nodes_ordered:
            if not _clk_low_power_closed(node):
                continue
            rows.append(
                {
                    "name": node.name,
                    "freq": node.freq,
                    "freq_label": _format_freq_hz(node.freq)
                    if node.freq is not None and node.freq > 0
                    else "",
                }
            )
        return rows

    @computed_field  # type: ignore[prop-decorator]
    @property
    def configurable_plls(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for node in self.tree.nodes_ordered:
            if node.kind != "pll":
                continue
            if node.output_groups:
                for group in node.output_groups:
                    rows.append(
                        {
                            "name": f'{node.name}["{group}"]',
                            "freq": node.freq_for_group(group),
                            "freq_label": _format_freq_hz(node.freq_for_group(group)),
                        }
                    )
            else:
                rows.append(
                    {
                        "name": node.name,
                        "freq": node.freq,
                        "freq_label": _format_freq_hz(node.freq),
                    }
                )
        return rows

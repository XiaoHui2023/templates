from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

from nodes import Tree
from reg_paths import (
    CPU_GATE_HCLK_GROUP,
    CPU_GATE_PASS_THROUGH_GROUP,
    CPU_GATE_PRIMARY_GROUP,
    DIV_KIND_TO_SV_ENUM,
    INV_KIND_TO_SV_ENUM,
    PLL_REG_KEYS,
    SOURCE_KIND_TO_SV_ENUM,
    RegBindingRow,
    any_node_path,
    tree_has_path_and_reg,
    any_reg_configured as tree_has_node_regs,
    collect_div_sv_classes,
    collect_inv_sv_classes,
    collect_pll_sv_classes,
    collect_source_sv_classes,
    iter_reg_bindings,
)

_MAX_FREQ_HZ = 5_000_000_000


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
        0.01,
        gt=0.0,
        lt=1.0,
        description="相邻周期相对偏差上限。",
    )
    duty_min: float = Field(
        50.0,
        ge=0.0,
        le=100.0,
        description="允许占空比下限，百分数；闭区间端点计入合格。",
    )
    duty_max: float = Field(
        66.0,
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
        1_000,
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
                f"min_freq_hz ({self.min_freq_hz}) 须不大于 "
                f"max_freq_hz ({self.max_freq_hz})"
            )
        return self

    @model_validator(mode="after")
    def _validate_duty_range(self) -> Settings:
        if self.duty_min > self.duty_max:
            raise ValueError(
                f"duty_min ({self.duty_min}) 须不大于 duty_max ({self.duty_max})"
            )
        return self

    @model_validator(mode="after")
    def _validate_pll_sc_fbdiv_range(self) -> Settings:
        if self.pll_sc_fbdiv_min > self.pll_sc_fbdiv_max:
            raise ValueError(
                f"pll_sc_fbdiv_min ({self.pll_sc_fbdiv_min}) 须不大于 "
                f"pll_sc_fbdiv_max ({self.pll_sc_fbdiv_max})"
            )
        return self

    @field_validator("class_regmodel")
    @classmethod
    def _validate_class_regmodel(cls, value: str) -> str:
        if not value:
            return value
        if not _SV_TYPE.match(value):
            raise ValueError(
                f"class_regmodel {value!r} 须为合法 SystemVerilog 类型名"
            )
        return value


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trees: List[Tree] = Field(
        ...,
        min_length=1,
        description="时钟树。",
    )
    settings: Settings = Field(
        default_factory=Settings,
        description="全局选项。",
    )

    @model_validator(mode="after")
    def _validate_regmodel_when_nodes_have_regs(self) -> Models:
        if self.any_regs_configured and not self.settings.class_regmodel:
            raise ValueError(
                "任意节点配置了 reg 或 regs 时须在 settings 中填写 class_regmodel"
            )
        return self

    @model_validator(mode="after")
    def _validate_tree_names_unique(self) -> Models:
        seen: set[str] = set()
        for tree in self.trees:
            if tree.name in seen:
                raise ValueError(f"trees 中 name {tree.name!r} 重复")
            seen.add(tree.name)
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 PLL 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def pll_sv_classes(self) -> List[str]:
        kinds: set[str] = set()
        for tree in self.trees:
            kinds.update(collect_pll_sv_classes(tree))
        return sorted(kinds)

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 div 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def div_sv_classes(self) -> List[str]:
        kinds: set[str] = set()
        for tree in self.trees:
            kinds.update(collect_div_sv_classes(tree))
        return sorted(kinds)

    @computed_field(  # type: ignore[prop-decorator]
        description="各 tree 所用 inv 型号对应的 SV 类名列表；YAML 与 model_validate 不可传入。",
    )
    @property
    def inv_sv_classes(self) -> List[str]:
        kinds: set[str] = set()
        for tree in self.trees:
            kinds.update(collect_inv_sv_classes(tree))
        return sorted(kinds)

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
        kinds: set[str] = set()
        for tree in self.trees:
            kinds.update(collect_source_sv_classes(tree))
        return sorted(kinds)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_kind_to_sv_enum(self) -> Dict[str, str]:
        return dict(SOURCE_KIND_TO_SV_ENUM)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pll_reg_keys_by_kind(self) -> Dict[str, List[str]]:
        return {kind: sorted(keys) for kind, keys in PLL_REG_KEYS.items()}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def any_regs_configured(self) -> bool:
        return any(tree_has_node_regs(tree) for tree in self.trees)

    @computed_field(  # type: ignore[prop-decorator]
        description="分别存在带 path 的节点与带 reg(regs) 的节点时为真；YAML 与 model_validate 不可传入。",
    )
    @property
    def enable_node_fix(self) -> bool:
        return any(tree_has_path_and_reg(tree) for tree in self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def regs_enabled(self) -> bool:
        return bool(self.settings.class_regmodel) and self.any_regs_configured

    @computed_field(  # type: ignore[prop-decorator]
        description="enable_node_fix、regs_enabled、any_node_path 均为真时生成 test_route；不可传入。",
    )
    @property
    def route_test_enabled(self) -> bool:
        return (
            self.enable_node_fix
            and self.regs_enabled
            and self.any_node_path
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cpu_gate_primary_group(self) -> str:
        return CPU_GATE_PRIMARY_GROUP

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cpu_gate_pass_through_group(self) -> str:
        return CPU_GATE_PASS_THROUGH_GROUP

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cpu_gate_hclk_group(self) -> str:
        return CPU_GATE_HCLK_GROUP

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inno_pll_primary_group(self) -> str:
        return "0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_bindings(self) -> List[RegBindingRow]:
        out: List[RegBindingRow] = []
        for tree in self.trees:
            out.extend(iter_reg_bindings(tree))
        return out

    @computed_field  # type: ignore[prop-decorator]
    @property
    def any_node_path(self) -> bool:
        return any(any_node_path(tree) for tree in self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_clk_name(self) -> Optional[str]:
        for tree in self.trees:
            for node in tree.nodes_ordered:
                if node.kind == "clk":
                    return node.name
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_clk_tree_name(self) -> Optional[str]:
        for tree in self.trees:
            for node in tree.nodes_ordered:
                if node.kind == "clk":
                    return tree.name
        return None

from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

from nodes import Tree
from reg_paths import (
    PLL_REG_KEYS,
    RegBindingRow,
    any_node_path,
    tree_has_path_and_reg,
    any_reg_configured as tree_has_node_regs,
    collect_pll_sv_classes,
    iter_reg_bindings,
)


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
        500,
        ge=500,
        description="仍活动的最低频率，单位 Hz。",
    )
    stable_cycles: int = Field(
        3,
        ge=2,
        description="连续稳定所需周期数。",
    )
    period_tolerance: float = Field(
        0.05,
        gt=0.0,
        lt=1.0,
        description="相邻周期相对偏差上限。",
    )
    duty_min: float = Field(
        33.0,
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
    @field_validator("duty_min", "duty_max", mode="before")
    @classmethod
    def _duty_as_percent(cls, v: object) -> object:
        if isinstance(v, (int, float)) and 0.0 < float(v) <= 1.0:
            return float(v) * 100.0
        return v

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

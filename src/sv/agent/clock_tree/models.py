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
    any_node_path_and_reg,
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
        description="可判定为仍活动的最低频率 Hz，非最高时钟；用于超时与最长可测周期 1/min_freq_hz 秒。",
    )
    stable_cycles: int = Field(
        3,
        ge=2,
        description="连续多少个周期落在容差内则置 stable。",
    )
    period_tolerance: float = Field(
        0.05,
        gt=0.0,
        lt=1.0,
        description="判定 stable 时相邻周期相对偏差上限。",
    )
    duty_min: float = Field(
        0.50,
        ge=0.0,
        le=1.0,
        description="允许占空比下限，份额 0～1，默认 0.50。",
    )
    duty_max: float = Field(
        0.66,
        ge=0.0,
        le=1.0,
        description="允许占空比上限，份额 0～1，默认 0.66。",
    )
    pll_lock_timeout_us: int = Field(
        1_000,
        ge=1,
        description="config_reg 等待各 pll lock 为 1 的最长时间，微秒。",
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
        description="为真时门控寄存器写 1 表示打开，config_reg 写入值与节点 open 一致；"
        "为假时写 1 表示关闭，按位取反后写入。",
    )
    div_reg_high_means_reset: bool = Field(
        False,
        description="为真时 div 的 rst 写 1 表示复位、写 0 表示不复位；"
        "为假时写 0 表示复位、写 1 表示不复位。"
        "config_reg 在 rst 上先写复位电平再写不复位电平。",
    )
    dto_reg_high_means_reset: bool = Field(
        False,
        description="为真时 dto 的 rst 写 1 表示复位、写 0 表示不复位；"
        "为假时写 0 表示复位、写 1 表示不复位。"
        "config_reg 在 rst 上先写复位电平再写不复位电平。",
    )
    @model_validator(mode="after")
    def _validate_duty_range(self) -> Settings:
        if self.duty_min >= self.duty_max:
            raise ValueError(
                f"duty_min ({self.duty_min}) 须小于 duty_max ({self.duty_max})"
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
        description="任一节点同时配置 path 与 reg(regs) 时为真；YAML 与 model_validate 不可传入。",
    )
    @property
    def enable_node_fix(self) -> bool:
        return any(any_node_path_and_reg(tree) for tree in self.trees)

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

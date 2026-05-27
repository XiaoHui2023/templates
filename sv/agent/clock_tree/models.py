from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

from nodes import Tree
from reg_paths import (
    any_gate_reg_configured,
    any_reg_configured,
    collect_div_reg_keys,
    collect_dto_reg_keys,
    collect_pll_reg_keys,
    iter_reg_bindings,
)

SettingDefType = Literal["str", "int", "bit"]


class SettingDef(BaseModel):
    name: str = Field(..., min_length=1, description="设置项名，兼作 settings 与每棵 tree 的 settings 键名。")
    type: SettingDefType = Field(
        ...,
        description="展开后 settings 成员类型：str、int、bit。",
    )
    default: Any = Field(..., description="settings.new 中的初值。")


class Models(BaseModel):
    setting_defs: List[SettingDef] = Field(
        default_factory=list,
        description="全局设置项声明列表；各 tree.settings 的键须与此一致。",
    )
    trees: List[Tree] = Field(..., min_length=1, description="时钟树列表，每棵含 nodes 与 settings。")
    vars: Dict[str, Any] = Field(
        default_factory=dict,
        description="用户自定义变量，模板内以 vars 引用，不做校验。",
    )
    class_prefix: str = Field(
        "clk_tree_",
        min_length=1,
        description="类型名前缀，与固定后缀拼接；建议含末尾下划线。",
    )
    class_regmodel: str = Field(
        "",
        description="RAL 根块类型名；connect 建树函数入参类型。",
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

    @model_validator(mode="after")
    def _validate_duty_range(self) -> Models:
        if self.duty_min >= self.duty_max:
            raise ValueError(
                f"duty_min ({self.duty_min}) 须小于 duty_max ({self.duty_max})"
            )
        return self

    @model_validator(mode="after")
    def _validate_setting_defs(self) -> Models:
        names = [d.name for d in self.setting_defs]
        if len(names) != len(set(names)):
            dup = {x for x in names if names.count(x) > 1}
            raise ValueError(f"setting_defs.name 须唯一，重复: {sorted(dup)}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def div_reg_keys(self) -> List[str]:
        return collect_div_reg_keys(self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dto_reg_keys(self) -> List[str]:
        return collect_dto_reg_keys(self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pll_reg_keys(self) -> List[str]:
        return collect_pll_reg_keys(self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gate_reg_enabled(self) -> bool:
        return any_gate_reg_configured(self.trees)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_bindings(self) -> List[tuple[str, str, str, str]]:
        return iter_reg_bindings(self.trees)

    @model_validator(mode="after")
    def _validate_regmodel(self) -> Models:
        if any_reg_configured(self.trees) and not self.class_regmodel.strip():
            raise ValueError(
                "节点配置了寄存器路径时 class_regmodel 须非空"
            )
        if self.class_regmodel and not _SV_TYPE.match(self.class_regmodel):
            raise ValueError(
                f"class_regmodel {self.class_regmodel!r} 须为合法 SystemVerilog 类型名"
            )
        return self

    @model_validator(mode="after")
    def _validate_trees(self) -> Models:
        tree_names = [t.name for t in self.trees]
        if len(tree_names) != len(set(tree_names)):
            dup = {x for x in tree_names if tree_names.count(x) > 1}
            raise ValueError(f"trees.name 须唯一，重复: {sorted(dup)}")

        expected = {d.name for d in self.setting_defs}
        for tree in self.trees:
            keys = set(tree.settings.keys())
            if keys != expected:
                raise ValueError(
                    f"tree {tree.name!r} 的 settings 键须与 setting_defs 一致: "
                    f"期望 {sorted(expected)}, 实际 {sorted(keys)}"
                )
        return self

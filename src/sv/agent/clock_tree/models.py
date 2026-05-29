from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

from nodes import Tree
from reg_paths import (
    PLL_REG_KEYS,
    RegBindingRow,
    any_node_path,
    collect_pll_sv_classes,
    iter_reg_bindings,
)


class Models(BaseModel):
    tree: Tree = Field(..., description="本 agent 对应的单棵时钟树，含 nodes。")
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
        ...,
        min_length=1,
        description="RAL 根块类型名；tree 的 build 入参类型。",
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
        10_000,
        ge=1,
        description="config_reg 等待各 pll lock 为 1 的最长时间，微秒。",
    )

    @model_validator(mode="after")
    def _validate_duty_range(self) -> Models:
        if self.duty_min >= self.duty_max:
            raise ValueError(
                f"duty_min ({self.duty_min}) 须小于 duty_max ({self.duty_max})"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pll_sv_classes(self) -> List[str]:
        return collect_pll_sv_classes(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pll_reg_keys_by_kind(self) -> Dict[str, List[str]]:
        return {kind: sorted(keys) for kind, keys in PLL_REG_KEYS.items()}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_bindings(self) -> List[RegBindingRow]:
        return iter_reg_bindings(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def any_node_path(self) -> bool:
        return any_node_path(self.tree)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_clk_name(self) -> Optional[str]:
        for node in self.tree.nodes_ordered:
            if node.kind == "clk":
                return node.name
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_clk_tree_name(self) -> Optional[str]:
        if self.first_clk_name is None:
            return None
        return self.tree.name

    @field_validator("class_regmodel")
    @classmethod
    def _validate_class_regmodel(cls, value: str) -> str:
        if not _SV_TYPE.match(value):
            raise ValueError(
                f"class_regmodel {value!r} 须为合法 SystemVerilog 类型名"
            )
        return value

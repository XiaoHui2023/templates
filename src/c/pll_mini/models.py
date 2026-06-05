from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator

_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from nodes import Tree
from plan import SettingsView, build_config_plan
from regmodel import Reg, RegModelIndex


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    main_fn: str = Field(
        "pll_mini_config",
        min_length=1,
        description="生成 C 源文件中配置入口函数名。",
    )
    header_guard: str = Field(
        "PLL_MINI_H",
        min_length=1,
        description="头文件 include guard 宏名。",
    )
    reg_write_fn: str = Field(
        "pll_mini_reg_write",
        min_length=1,
        description="寄存器写函数名；由生成代码定义，供配置步骤调用。",
    )
    gate_reg_high_means_open: bool = Field(
        False,
        description="为真时门控寄存器写 1 表示打开；为假时写 1 表示关闭。",
    )
    div_reg_high_means_reset: bool = Field(
        False,
        description="为真时 div 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )
    dto_reg_high_means_reset: bool = Field(
        False,
        description="为真时 dto 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )
    lock_timeout_us: int = Field(
        1_000,
        ge=1,
        description="轮询 PLL lock 的最长时间，微秒。",
    )

    @model_validator(mode="after")
    def _validate_identifiers(self) -> Settings:
        for name, value in (
            ("main_fn", self.main_fn),
            ("header_guard", self.header_guard),
            ("reg_write_fn", self.reg_write_fn),
        ):
            if not _C_IDENT.match(value):
                raise ValueError(f"{name} {value!r} 须为合法 C 标识符")
        return self


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tree: Tree = Field(..., description="单棵时钟树。")
    regmodel: List[Reg] = Field(
        ...,
        min_length=1,
        description="寄存器模型列表。",
    )
    settings: Settings = Field(
        default_factory=Settings,
        description="全局选项。",
    )

    @property
    def config_steps(self):
        s = self.settings
        return build_config_plan(
            self.tree,
            RegModelIndex(self.regmodel),
            SettingsView(
                gate_reg_high_means_open=s.gate_reg_high_means_open,
                div_reg_high_means_reset=s.div_reg_high_means_reset,
                dto_reg_high_means_reset=s.dto_reg_high_means_reset,
                lock_timeout_us=s.lock_timeout_us,
            ),
        )

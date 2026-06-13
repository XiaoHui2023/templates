from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationInfo,
    model_validator,
)

_C_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from nodes import Tree
from plan import SettingsView, build_config_plan
from ralf_load import load_regmodel_from_ralf
from regmodel import Reg, RegModelIndex
from resolve import resolve_tree


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
    consolver_timeout_ms: int | None = Field(
        None,
        ge=1,
        description="consolver 求解超时，毫秒；省略则不限时。",
    )

    @model_validator(mode="after")
    def _validate_identifiers(self) -> Settings:
        for name, value in (
            ("main_fn", self.main_fn),
            ("header_guard", self.header_guard),
        ):
            if not _C_IDENT.match(value):
                raise ValueError(f"{name} {value!r} 须为合法 C 标识符")
        return self

    @model_validator(mode="after")
    def _validate_pll_sc_fbdiv_range(self) -> Settings:
        if self.pll_sc_fbdiv_min > self.pll_sc_fbdiv_max:
            raise ValueError(
                f"pll_sc_fbdiv_min ({self.pll_sc_fbdiv_min}) 须不大于 "
                f"pll_sc_fbdiv_max ({self.pll_sc_fbdiv_max})"
            )
        return self


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ralf: str = Field(..., min_length=1, description="RALF 文件路径。")
    ralf_include_dirs: List[str] = Field(
        default_factory=list,
        description="RALF source 搜索目录列表。",
    )
    ralf_base_offset: int = Field(
        0,
        ge=0,
        description="加到 ralf-conv 全部寄存器绝对地址上的字节偏移。",
    )
    tree: Tree = Field(..., description="单棵时钟树。")
    settings: Settings = Field(
        default_factory=Settings,
        description="全局选项。",
    )

    _regmodel: List[Reg] = PrivateAttr(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_tree_input(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "tree" in data:
            return data

        if "trees" in data:
            trees = data["trees"]
            if not isinstance(trees, list) or len(trees) != 1:
                raise ValueError("pll_mini 只接受一棵 clock tree")
            return {**data, "tree": trees[0]}

        if "nodes" in data:
            tree_name = data.get("name", "main")
            return {
                **data,
                "tree": {
                    "name": tree_name,
                    "nodes": data["nodes"],
                },
            }

        return data

    @model_validator(mode="after")
    def _load_regmodel(self, info: ValidationInfo) -> Models:
        yaml_dir: Path | None = None
        ctx = info.context or {}
        raw_dir = ctx.get("yaml_dir")
        if isinstance(raw_dir, (str, Path)):
            yaml_dir = Path(raw_dir)
        regs = load_regmodel_from_ralf(
            self.ralf,
            yaml_dir=yaml_dir,
            include_dirs=self.ralf_include_dirs,
            base_offset=self.ralf_base_offset,
        )
        object.__setattr__(self, "_regmodel", regs)
        return self

    @property
    def regmodel(self) -> List[Reg]:
        return list(self._regmodel)

    @property
    def tree_resolve(self):
        s = self.settings
        return resolve_tree(
            self.tree,
            pll_sc_fbdiv_min=s.pll_sc_fbdiv_min,
            pll_sc_fbdiv_max=s.pll_sc_fbdiv_max,
            consolver_timeout_ms=s.consolver_timeout_ms,
        )

    @property
    def config_plan(self):
        s = self.settings
        return build_config_plan(
            self.tree,
            RegModelIndex(self.regmodel),
            SettingsView(
                gate_reg_high_means_open=s.gate_reg_high_means_open,
                div_reg_high_means_reset=s.div_reg_high_means_reset,
                dto_reg_high_means_reset=s.dto_reg_high_means_reset,
            ),
            self.tree_resolve,
        )

    @classmethod
    def model_validate_with_yaml_dir(
        cls,
        obj: object,
        *,
        yaml_dir: Path | str | None = None,
    ) -> Models:
        ctx = {"yaml_dir": str(yaml_dir)} if yaml_dir is not None else None
        return cls.model_validate(obj, context=ctx)

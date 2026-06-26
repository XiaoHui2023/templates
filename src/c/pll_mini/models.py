from __future__ import annotations

import re
import threading
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
from plan import ConfigPlan, SettingsView, build_config_plan, collect_used_regs
from ralf_load import load_regmodel_from_ralf
from regmodel import Reg, RegModelIndex
from resolve import TreeResolve, resolve_tree
from tools import log_stage_done, log_stage_start

_ModelCacheKey = tuple[str, str, tuple[str, ...]]
_CACHE_LOCK = threading.RLock()
_TREE_RESOLVE_CACHE: dict[_ModelCacheKey, TreeResolve] = {}
_TREE_RESOLVE_ERROR_CACHE: dict[_ModelCacheKey, str] = {}
_CONFIG_PLAN_CACHE: dict[_ModelCacheKey, ConfigPlan] = {}
_HEADER_REGS_CACHE: dict[_ModelCacheKey, List[Reg]] = {}


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
    source_guard: str = Field(
        "PLL_MINI_C",
        min_length=1,
        description="源文件 include guard 宏名，避免被多次 include。",
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
    period_tolerance: float = Field(
        0.01,
        ge=0,
        le=1,
        description="分频求解允许的相对频率偏差。",
    )
    reg_base_offset: int = Field(
        0,
        ge=0,
        description="寄存器整体偏移地址。",
    )

    @model_validator(mode="after")
    def _validate_identifiers(self) -> Settings:
        for name, value in (
            ("main_fn", self.main_fn),
            ("header_guard", self.header_guard),
            ("source_guard", self.source_guard),
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
        description="RALF 引用其它文件时的额外搜索目录。",
    )
    tree: Tree = Field(..., description="单棵时钟树。")
    settings: Settings = Field(
        default_factory=Settings,
        description="全局选项。",
    )

    _regmodel: List[Reg] = PrivateAttr(default_factory=list)
    _tree_resolve: TreeResolve | None = PrivateAttr(default=None)
    _config_plan: ConfigPlan | None = PrivateAttr(default=None)
    _header_regs: List[Reg] | None = PrivateAttr(default=None)

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
        started_at = log_stage_start(
            "models",
            "load",
            "regmodel",
            ralf=self.ralf,
            include_dirs=len(self.ralf_include_dirs),
        )
        regs = load_regmodel_from_ralf(
            self.ralf,
            yaml_dir=yaml_dir,
            include_dirs=self.ralf_include_dirs,
            base_offset=self.settings.reg_base_offset,
        )
        log_stage_done("models", "load", "regmodel", started_at, regs=len(regs))
        object.__setattr__(self, "_regmodel", regs)
        return self

    @property
    def regmodel(self) -> List[Reg]:
        return list(self._regmodel)

    def _cache_key(self) -> _ModelCacheKey:
        return (
            self.tree.model_dump_json(),
            self.settings.model_dump_json(),
            tuple(reg.model_dump_json() for reg in self._regmodel),
        )

    @property
    def tree_resolve(self) -> TreeResolve:
        with _CACHE_LOCK:
            if self._tree_resolve is not None:
                return self._tree_resolve
            key = self._cache_key()
            cached = _TREE_RESOLVE_CACHE.get(key)
            if cached is not None:
                self._tree_resolve = cached
                return cached
            cached_error = _TREE_RESOLVE_ERROR_CACHE.get(key)
            if cached_error is not None:
                raise RuntimeError(cached_error)
            s = self.settings
            started_at = log_stage_start(
                "models",
                "compute",
                "tree_resolve",
                nodes=len(self.tree.nodes),
            )
            try:
                result = resolve_tree(
                    self.tree,
                    pll_sc_fbdiv_min=s.pll_sc_fbdiv_min,
                    pll_sc_fbdiv_max=s.pll_sc_fbdiv_max,
                    consolver_timeout_ms=s.consolver_timeout_ms,
                    period_tolerance=s.period_tolerance,
                    reg_index=RegModelIndex(self.regmodel),
                )
            except RuntimeError as exc:
                log_stage_done(
                    "models",
                    "compute",
                    "tree_resolve",
                    started_at,
                    failed=True,
                )
                _TREE_RESOLVE_ERROR_CACHE[key] = str(exc)
                raise
            log_stage_done(
                "models",
                "compute",
                "tree_resolve",
                started_at,
                nodes=len(result.by_name),
            )
            _TREE_RESOLVE_CACHE[key] = result
            self._tree_resolve = result
            return result

    @property
    def config_plan(self) -> ConfigPlan:
        with _CACHE_LOCK:
            if self._config_plan is not None:
                return self._config_plan
            key = self._cache_key()
            cached = _CONFIG_PLAN_CACHE.get(key)
            if cached is not None:
                self._config_plan = cached
                return cached
            s = self.settings
            started_at = log_stage_start(
                "models",
                "compute",
                "config_plan",
                nodes=len(self.tree.nodes),
                regs=len(self._regmodel),
            )
            result = build_config_plan(
                self.tree,
                RegModelIndex(self.regmodel),
                SettingsView(
                    gate_reg_high_means_open=s.gate_reg_high_means_open,
                    div_reg_high_means_reset=s.div_reg_high_means_reset,
                    dto_reg_high_means_reset=s.dto_reg_high_means_reset,
                ),
                self.tree_resolve,
            )
            log_stage_done(
                "models",
                "compute",
                "config_plan",
                started_at,
                pll_instances=len(result.pll_instances),
                dev_steps=len(result.dev_steps),
            )
            _CONFIG_PLAN_CACHE[key] = result
            self._config_plan = result
            return result

    @property
    def header_regs(self) -> List[Reg]:
        with _CACHE_LOCK:
            if self._header_regs is not None:
                return list(self._header_regs)
            key = self._cache_key()
            cached = _HEADER_REGS_CACHE.get(key)
            if cached is not None:
                self._header_regs = cached
                return list(cached)
            started_at = log_stage_start(
                "models",
                "compute",
                "header_regs",
                regs=len(self._regmodel),
            )
            index = RegModelIndex(self.regmodel)
            result = list(collect_used_regs(index, self.config_plan))
            log_stage_done(
                "models",
                "compute",
                "header_regs",
                started_at,
                regs=len(result),
            )
            _HEADER_REGS_CACHE[key] = result
            self._header_regs = result
            return list(result)

    @classmethod
    def model_validate_with_yaml_dir(
        cls,
        obj: object,
        *,
        yaml_dir: Path | str | None = None,
    ) -> Models:
        ctx = {"yaml_dir": str(yaml_dir)} if yaml_dir is not None else None
        return cls.model_validate(obj, context=ctx)

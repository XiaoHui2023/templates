from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Callable, Dict, List

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field, field_validator, model_validator

from node.python.base import Node, Tree, validate_nodes_graph
from node.python.registry import parse_plugin_settings
from reg_paths import RegBindingRow, analyze_reg_bindings, any_reg_configured
from schema_error import ERR

_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class Settings(BaseModel):
    """全局设置与插件命名空间。"""

    model_config = ConfigDict(extra="forbid")

    class_prefix: str = "clk_tree_"
    class_regmodel: str = ""
    direct_config: bool = False
    min_freq_hz: int = Field(15_000, ge=1)
    max_freq_hz: int = Field(5_000_000_000, ge=1)
    active_cycles: int = Field(1, ge=1)
    stable_cycles: int = Field(3, ge=2)
    period_tolerance: float = Field(0.02, gt=0.0, lt=1.0)
    duty_min: float = Field(48.0, ge=0.0, le=100.0)
    duty_max: float = Field(67.0, ge=0.0, le=100.0)
    duty_tolerance_pct: float = Field(0.05, ge=0.0, le=10.0)
    plugin: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("plugin")
    @classmethod
    def _plugin_settings_are_valid(cls, value: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            scope: settings.model_dump(exclude_unset=True, exclude_none=True)
            for scope, settings in (
                (scope, parse_plugin_settings(scope, fields))
                for scope, fields in value.items()
            )
        }

    @field_validator("class_prefix")
    @classmethod
    def _prefix_is_identifier(cls, value: str) -> str:
        if not _SV_TYPE.match(value):
            raise ValueError(f"{ERR.field('class_prefix')} {value!r} 须为合法 SystemVerilog 名字")
        return value

    @field_validator("class_regmodel")
    @classmethod
    def _regmodel_is_identifier(cls, value: str) -> str:
        if value and not _SV_TYPE.match(value):
            raise ValueError(f"{ERR.field('class_regmodel')} {value!r} 须为合法 SystemVerilog 类型名")
        return value

    @model_validator(mode="after")
    def _range_is_valid(self) -> "Settings":
        if self.min_freq_hz > self.max_freq_hz:
            raise ValueError(f"{ERR.field('min_freq_hz')} 须不大于 {ERR.field('max_freq_hz')}")
        if self.duty_min > self.duty_max:
            raise ValueError(f"{ERR.field('duty_min')} 须不大于 {ERR.field('duty_max')}")
        return self

    def plugin_value(self, plugin_name: str, key: str, default: Any) -> Any:
        return self.plugin.get(plugin_name, {}).get(key, default)

    def plugin_fraction(
            self,
            plugin_name: str,
            key: str,
            default: float) -> tuple[int, int]:
        """Return one plugin setting as an exact positive decimal fraction.

        Args:
            plugin_name: Plugin-owned settings namespace.
            key: Setting name inside the namespace.
            default: Decimal-compatible fallback value.

        Returns:
            Numerator and denominator suitable for generated integral SV math.

        Raises:
            ValueError: The configured value is not a positive finite decimal.
        """
        value = self.plugin_value(plugin_name, key, default)
        try:
            decimal = Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"plugin.{plugin_name}.{key} 须为正数") from exc
        if not decimal.is_finite() or decimal <= 0:
            raise ValueError(f"plugin.{plugin_name}.{key} 须为正数")
        exponent = decimal.as_tuple().exponent
        denominator = 1 if exponent >= 0 else 10 ** (-exponent)
        numerator = int(decimal * denominator)
        return numerator, denominator

    @property
    def tolerance_den(self) -> int:
        exponent = Decimal(str(self.period_tolerance)).as_tuple().exponent
        return 1 if exponent >= 0 else 10 ** (-exponent)


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _cache: Dict[str, Any] = PrivateAttr(default_factory=dict)

    nodes: Dict[str, Node] = Field(..., min_length=1)
    settings: Settings = Field(default_factory=Settings)

    @model_validator(mode="before")
    @classmethod
    def _parse_document(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("时钟树输入须为对象")
        if "nodes" in data:
            raise ValueError(f"{ERR.field('nodes')} 不再支持；节点须直接位于根对象")
        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError(f"{ERR.field('settings')} 须为对象")
        return {"settings": settings, "nodes": {key: value for key, value in data.items() if key != "settings"}}

    def _cached(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    def plugin_value(self, plugin_name: str, key: str, default: Any) -> Any:
        """Expose one opaque plugin setting to its own template.

        Args:
            plugin_name: Plugin-owned settings namespace.
            key: Setting name inside that namespace.
            default: Value used when the plugin does not set it.
        """
        return self.settings.plugin_value(plugin_name, key, default)

    def plugin_fraction(self, plugin_name: str, key: str, default: float) -> tuple[int, int]:
        """Expose one exact decimal setting as integral SV operands.

        Args:
            plugin_name: Plugin-owned settings namespace.
            key: Decimal setting name.
            default: Positive fallback value.
        """
        return self.settings.plugin_fraction(plugin_name, key, default)

    @field_validator("nodes", mode="before")
    @classmethod
    def _validate_nodes(cls, value: Any) -> Any:
        return Tree.model_validate({"nodes": value}).nodes

    @model_validator(mode="after")
    def _validate_model(self) -> "Models":
        validate_nodes_graph(self.nodes)
        if not any_reg_configured(self.tree):
            raise ValueError(f"至少须配置一个 {ERR.fields('reg', 'regs')}")
        if not self.settings.class_regmodel:
            raise ValueError(f"任意节点配置了 {ERR.fields('reg', 'regs')} 时须填写 {ERR.field('settings.class_regmodel')}")
        self._cache["reg_analysis"] = analyze_reg_bindings(self.tree)
        return self

    @computed_field
    @property
    def tree(self) -> Tree:
        return self._cached("tree", lambda: Tree(nodes=self.nodes))

    @computed_field
    @property
    def reg_bindings(self) -> List[RegBindingRow]:
        return self._cache["reg_analysis"][0]

    @computed_field
    @property
    def shared_reg_constraints(self) -> list[tuple[str, str]]:
        return self._cache["reg_analysis"][1]

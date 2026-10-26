from __future__ import annotations

from typing import TypeAlias

from .config import NodePluginConfig, NodePluginSettings, OpaqueNodePluginConfig, OpaqueNodePluginSettings
from .plugins.cell import CellConfig
from .plugins.clk import ClkConfig
from .plugins.div_div import DivDivConfig, DivDivSettings
from .plugins.div_div_r import DivDivRConfig
from .plugins.div_dto import DivDtoConfig, DivDtoSettings
from .plugins.gate import GateConfig, GateSettings
from .plugins.inv import InvConfig
from .plugins.inv_cell import InvCellConfig
from .plugins.inv_mux import InvMuxConfig
from .plugins.mux import MuxConfig
from .plugins.pll_dw import PllDwConfig
from .plugins.pll_inno import PllInnoConfig
from .plugins.pll_sc import PllScConfig, PllScSettings
from .plugins.pll_tci import PllTciConfig
from .plugins.source import SourceNodeConfig
from .plugins.source_pad import SourcePadConfig
from .plugins._families import DividerSettings, InverterSettings, PllSettings

PluginConfigType: TypeAlias = type[NodePluginConfig]
PluginSettingsType: TypeAlias = type[NodePluginSettings]

PLUGIN_CONFIGS: dict[str, PluginConfigType] = {
    "cell": CellConfig,
    "clk": ClkConfig,
    "div_div": DivDivConfig,
    "div_div_r": DivDivRConfig,
    "div_dto": DivDtoConfig,
    "gate": GateConfig,
    "inv": InvConfig,
    "inv_cell": InvCellConfig,
    "inv_mux": InvMuxConfig,
    "mux": MuxConfig,
    "pll_dw": PllDwConfig,
    "pll_inno": PllInnoConfig,
    "pll_sc": PllScConfig,
    "pll_tci": PllTciConfig,
    "source": SourceNodeConfig,
    "source_pad": SourcePadConfig,
}

PLUGIN_SETTINGS: dict[str, PluginSettingsType] = {
    "divider": DividerSettings,
    "div_div": DivDivSettings,
    "div_dto": DivDtoSettings,
    "gate": GateSettings,
    "inverter": InverterSettings,
    "pll": PllSettings,
    "pll_sc": PllScSettings,
}


def parse_plugin_config(kind: str, values: dict[str, object]) -> NodePluginConfig:
    """按显式注册表校验一个节点配置。

    Args:
        kind: 节点声明的插件名
        values: 节点配置映射

    Returns:
        NodePluginConfig: 已校验的插件配置；未知插件保留不透明映射
    """
    config_type = PLUGIN_CONFIGS.get(kind, OpaqueNodePluginConfig)
    return config_type.model_validate(values)


def parse_plugin_settings(scope: str, values: dict[str, object]) -> NodePluginSettings:
    """按显式注册表校验一个插件全局设置作用域。"""
    settings_type = PLUGIN_SETTINGS.get(scope, OpaqueNodePluginSettings)
    return settings_type.model_validate(values)

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .base import NodeBase
from .plugins.cell import CellNode
from .plugins.clk import ClkNode
from .plugins.clk_div_with_clken import ClkDivWithClkenNode
from .plugins.div import DivNode
from .plugins.div_div import DivDivNode, DivSettings
from .plugins.div_div_r import DivFixedNode
from .plugins.div_dto import DivDtoNode, DtoSettings
from .plugins.gate import GateNode, GateSettings
from .plugins.inv import InvNode
from .plugins.inv_cell import InvCellNode
from .plugins.inv_mux import InvMuxNode
from .plugins.mux import MuxNode
from .plugins.pll import PllNode
from .plugins.pll_dw import PllDwNode
from .plugins.pll_inno import PllInnoNode
from .plugins.pll_sc import PllScNode, PllScSettings
from .plugins.pll_tci import PllTciNode
from .plugins.source import ClockSourceNode
from .plugins.source_pad import PadNode

PLUGIN_TYPES: dict[str, type[NodeBase]] = {
    "cell": CellNode,
    "clk": ClkNode,
    "div": DivNode,
    "gate": GateNode,
    "inv": InvNode,
    "mux": MuxNode,
    "pll": PllNode,
    "source": ClockSourceNode,
    "div_div": DivDivNode,
    "div_dto": DivDtoNode,
    "div_div_r": DivFixedNode,
    "pll_sc": PllScNode,
    "pll_tci": PllTciNode,
    "pll_dw": PllDwNode,
    "pll_inno": PllInnoNode,
    "inv_mux": InvMuxNode,
    "inv_cell": InvCellNode,
    "source_pad": PadNode,
    "clk_div_with_clken": ClkDivWithClkenNode,
}
ALIASES: dict[str, tuple[str, dict[str, str]]] = {
    "clock": ("clk", {}),
    "div_n": ("div", {"div_kind": "div_n"}),
    "dto": ("div", {"div_kind": "dto"}),
    "dto_n": ("div", {"div_kind": "dto_n"}),
    "div_r": ("div", {"div_kind": "div_r"}),
}
VARIANTS = {
    ("div", "div_kind", "div"): "div_div",
    ("div", "div_kind", "div_n"): "div_div",
    ("div", "div_kind", "dto"): "div_dto",
    ("div", "div_kind", "dto_n"): "div_dto",
    ("div", "div_kind", "div_r"): "div_div_r",
    ("pll", "pll_kind", "sc"): "pll_sc",
    ("pll", "pll_kind", "tci"): "pll_tci",
    ("pll", "pll_kind", "dw"): "pll_dw",
    ("pll", "pll_kind", "inno"): "pll_inno",
    ("inv", "inv_kind", "inv_mux"): "inv_mux",
    ("inv", "inv_kind", "inv_cell"): "inv_cell",
    ("source", "source_kind", "pad"): "source_pad",
}

PLUGIN_SETTINGS = (GateSettings, DivSettings, DtoSettings, PllScSettings)


def parse_plugin_settings(values: dict[str, object]) -> dict[str, object]:
    """将插件设置分别交给各自的配置模型。"""
    allowed = {key for schema in PLUGIN_SETTINGS for key in schema.model_fields}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"settings 未注册配置字段: {sorted(unknown)}")
    result = {}
    for schema in PLUGIN_SETTINGS:
        result.update(
            schema.model_validate(
                {
                    key: value
                    for key, value in values.items()
                    if key in schema.model_fields
                }
            ).model_dump()
        )
    return result


def default_plugin_settings(**common):
    """为独立调用者提供插件默认设置。"""
    from types import SimpleNamespace

    return SimpleNamespace(**parse_plugin_settings({}), **common)


def normalize_node_item(item: dict[str, Any]) -> dict[str, Any]:
    """按注册表转换节点别名，保留显式填写的配置。"""
    kind = item.get("kind")
    if isinstance(kind, str) and kind in ALIASES:
        canonical, defaults = ALIASES[kind]
        item = {**defaults, **item, "kind": canonical}
        kind = canonical
    for (family, field, value), plugin in VARIANTS.items():
        if (
            kind == family
            and str(item.get(field, "div" if family == "div" else "")).lower() == value
        ):
            return {**item, "kind": plugin, field: value}
    return item


def parse_node(name: str, item: object) -> NodeBase:
    """通过插件模型校验节点，并保留字段位置。

    Args:
        name: 节点字典键。
        item: 节点配置。

    Returns:
        已校验的插件实例。

    Raises:
        ValueError: 插件未注册或字段配置错误。
    """
    if not isinstance(item, dict):
        raise ValueError(f"nodes[{name!r}] 应为对象")
    values = normalize_node_item(item)
    kind = values.get("kind")
    node_type = PLUGIN_TYPES.get(kind) if isinstance(kind, str) else None
    if node_type is None:
        raise ValueError(
            f"nodes[{name!r}].kind={kind!r}: 未注册插件；可用插件: {', '.join(sorted(PLUGIN_TYPES))}"
        )
    try:
        return node_type.model_validate(values, context={"node_name": name})
    except ValidationError as exc:
        details = []
        for error in exc.errors():
            suffix = ".".join(str(part) for part in error["loc"])
            details.append(
                f"nodes[{name!r}]"
                + (f".{suffix}" if suffix else "")
                + f": {error['msg']}"
            )
        raise ValueError("\n".join(details)) from exc

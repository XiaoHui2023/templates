from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .base import NodeBase
from .discovery import discover

PLUGIN_TYPES, PLUGIN_SETTINGS = discover(__package__ + ".plugins")
INPUT_FORMS = {}
for _canonical, _plugin in PLUGIN_TYPES.items():
    for _form in _plugin.input_forms:
        INPUT_FORMS.setdefault(_form.kind, []).append((_canonical, _form))


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
    while True:
        kind = item.get("kind")
        matches = [
            (form, result)
            for canonical, form in (
                INPUT_FORMS.get(kind, ()) if isinstance(kind, str) else ()
            )
            if (result := form.normalize(item, canonical)) is not None
        ]
        if not matches:
            return item
        if len(matches) > 1:
            raise ValueError(f"ambiguous plugin input: {item!r}")
        form, item = matches[0]
        if not form.target_kind:
            return item


def parse_node(name: str, item: object, *, normalized: bool = False) -> NodeBase:
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
    values = item if normalized else normalize_node_item(item)
    kind = values.get("kind")
    node_type = PLUGIN_TYPES.get(kind) if isinstance(kind, str) else None
    if node_type is None:
        forms = INPUT_FORMS.get(kind, ()) if isinstance(kind, str) else ()
        selectors = "; ".join(
            f"{form.field}={form.values!r}" for _, form in forms if form.field
        )
        raise ValueError(
            f"nodes[{name!r}].kind={kind!r}: 未注册插件；可用插件: {', '.join(sorted(PLUGIN_TYPES))}"
            + (f"；该输入形式需要 {selectors}" if selectors else "")
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

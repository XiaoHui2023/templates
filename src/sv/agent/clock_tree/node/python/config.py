from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def sv_literal(value: object) -> str:
    """将一个插件配置值转换为 SystemVerilog 字面量。

    Args:
        value: 已由插件模型校验的标量值

    Returns:
        str: 可直接写入节点成员的字面量

    Raises:
        ValueError: 值不是支持的标量类型
    """
    if isinstance(value, bool):
        return "1'b1" if value else "1'b0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise ValueError(f"属性值 {value!r} 须为 bool、int、float 或 str")


class NodePluginConfig(BaseModel):
    """节点插件声明的显式配置字段。"""

    model_config = ConfigDict(extra="forbid")

    def normalize_outputs(self, outputs: list[str]) -> list[str]:
        """返回插件支持的输出组。

        Args:
            outputs: 用户声明的输出组

        Returns:
            list[str]: 校验后的输出组，默认保持原值
        """
        return outputs

    def port_paths_for_output(
            self, output: str, ports: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """返回一个输出组的端口路径。

        Args:
            output: 输出组名字
            ports: 节点声明的端口路径

        Returns:
            list[tuple[str, str, str]]: 角色、端口键和路径
        """
        return ports

    def sv_assignments(self) -> list[tuple[str, str]]:
        """导出用户明确填写的成员赋值。"""
        return [
            (field, sv_literal(value))
            for field, value in sorted(self.model_dump(exclude_unset=True, exclude_none=True).items())
        ]


class OpaqueNodePluginConfig(NodePluginConfig):
    """未在 Python 注册的节点保留其显式配置并交给 SV 编译检查。"""

    model_config = ConfigDict(extra="allow")
    @model_validator(mode="after")
    def _validate_values(self) -> "OpaqueNodePluginConfig":
        for field, value in (self.__pydantic_extra__ or {}).items():
            if not _SV_ID.match(field):
                raise ValueError(f"插件属性 {field!r} 须为合法 SystemVerilog 名字")
            sv_literal(value)
        return self

    def sv_assignments(self) -> list[tuple[str, str]]:
        """导出不透明节点的全部显式成员赋值。"""
        return [
            (field, sv_literal(value))
            for field, value in sorted((self.__pydantic_extra__ or {}).items())
        ]


class NodePluginSettings(BaseModel):
    """节点插件声明的全局设置字段。"""

    model_config = ConfigDict(extra="forbid")


class OpaqueNodePluginSettings(NodePluginSettings):
    """未注册插件的全局设置原样交给其 SV 模板。"""

    model_config = ConfigDict(extra="allow")

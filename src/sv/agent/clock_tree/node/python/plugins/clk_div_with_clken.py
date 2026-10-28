from __future__ import annotations

from typing import Literal

from pydantic import Field

from schema_error import ERR

from ..config import NodePluginSettings
from ._families import DividerConfig


class ClkDivWithClkenConfig(DividerConfig):
    """直通核心时钟及共享分频的两个输出。"""

    ratio: Literal[2, 3, 4, 6] | None = Field(default=None, description="分频比，2、3、4 或 6")

    def register_encoding(self, role: str, access: str) -> str | None:
        """返回分频字段的规范编码，默认 reg 与 div 指向同一字段。"""
        if role not in {"reg", "div"}:
            return None
        ratio = f"{access}._resolved_ratio"
        return f"({ratio} == 2 ? 0 : {ratio} == 3 ? 2 : {ratio} == 4 ? 4 : 8)"

    def normalize_outputs(self, outputs: list[str]) -> list[str]:
        """提供固定输出组，拒绝拼错或缺少的输出。

        Args:
            outputs: 用户声明的输出组，可省略

        Returns:
            list[str]: 按固定顺序排列的三个输出

        Raises:
            ValueError: 输出组不是器件的三个固定输出
        """
        expected = ["clk_arm_core", "hclk", "hclken"]
        if outputs and set(outputs) != set(expected):
            raise ValueError(f"{ERR.field('outputs')} 应为 {expected!r}")
        return expected

    def port_paths_for_output(
            self, output: str, ports: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """将具名输出路径分配给对应输出组。

        Args:
            output: 输出组名字
            ports: 节点声明的输入和输出路径

        Returns:
            list[tuple[str, str, str]]: 当前输出组的默认输入、输出路径

        Raises:
            ValueError: 使用默认输出路径或未知输出名
        """
        result = []
        for role, key, path in ports:
            if role == "out":
                if key not in {"clk_arm_core", "hclk", "hclken"}:
                    raise ValueError(f"使用 {ERR.field('out_paths')} 指定 clk_arm_core、hclk、hclken")
                if key == output:
                    result.append((role, "default", path))
            elif role == "in" and key == "default":
                result.append((role, key, path))
            else:
                raise ValueError(f"该节点使用 {ERR.fields('in_path', 'out_paths')}")
        return result


class ClkDivWithClkenSettings(NodePluginSettings):
    """分频配置的复位、load 和等待设置。"""

    reg_high_means_reset: bool = Field(default=False, description="复位高有效")
    settle_ns: int = Field(default=200, ge=0, description="配置后测量前等待时间，ns")

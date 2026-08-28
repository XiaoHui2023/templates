from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FieldNode(BaseModel):
    """单个 field：`inner_statements` 按源顺序保存每条完整语句（含分号）。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    paren_path: str | None = Field(
        default=None,
        description="紧跟在 field 名后的圆括号路径内容（不含括号），如 ``field f(hdl.sig)``",
    )
    offset_bits: int | None = Field(default=None, description="field 内 `@` 后的位偏移")
    inner_statements: list[str] = Field(
        default_factory=list,
        description='field 花括号内语句，如 bits 1;、reset \'h0;、enum { ... };',
    )


class RegisterNode(BaseModel):
    """寄存器：可为完整 `{ ... }` 定义，或仅 `register name;` 的前向引用。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    paren_path: str | None = Field(
        default=None,
        description="紧跟在 register 名后的圆括号路径内容（不含括号），如 ``register r (dut.reg)``",
    )
    offset_bytes: int | None = Field(default=None, description="register 后的 `@` 字节偏移")
    bytes_width: int | None = None
    fields: list[FieldNode] = Field(default_factory=list)
    declaration_only: bool = False


class BlockNode(BaseModel):
    """层次化 block。

    典型形态：
    - 定义体：``block 名 { ... }``
    - 简单映射：``block 名 @地址;``
    - 实例化：``block 左名 = 右名 [ (路径) ] [ @地址 ] ;`` 或带 ``{ ... }``
    - 带路径实例化：``block 名 (hdl路径) @地址;``（无 ``=`` 右名）
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    rhs_head: str | None = Field(
        default=None,
        description="`=` 右侧起始的层级名（含可能的 `[..]` 后缀）",
    )
    rhs_paren_path: str | None = Field(
        default=None,
        description="圆括号路径（不含括号）：``=`` 形式下紧跟 rhs_head；无 ``=`` 时紧跟 block 名",
    )
    base_address: int | None = Field(
        default=None,
        description="`@` 后的地址；可出现于简单 `block 名 @addr` 或 `=` 形式末尾",
    )
    has_body: bool = Field(
        default=True,
        description="是否带有 `{ ... }`；仅分号结尾的声明为 False",
    )
    bytes_width: int | None = None
    registers: list[RegisterNode] = Field(default_factory=list)
    blocks: list[BlockNode] = Field(default_factory=list)


class SystemNode(BaseModel):
    """层次化 system；体内可嵌套 system 与 block，不含 register。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    rhs_head: str | None = Field(
        default=None,
        description="`=` 右侧起始的层级名（含可能的 `[..]` 后缀）",
    )
    rhs_paren_path: str | None = Field(
        default=None,
        description="圆括号路径（不含括号）：``=`` 形式下紧跟 rhs_head；无 ``=`` 时紧跟 system 名",
    )
    base_address: int | None = Field(
        default=None,
        description="`@` 后的地址；可出现于简单 `system 名 @addr` 或 `=` 形式末尾",
    )
    has_body: bool = Field(
        default=True,
        description="是否带有 `{ ... }`；仅分号结尾的声明为 False",
    )
    bytes_width: int | None = None
    systems: list[SystemNode] = Field(default_factory=list)
    blocks: list[BlockNode] = Field(default_factory=list)


class RalfDocument(BaseModel):
    """顶层 RALF 文件内容（顶层为若干 `system`；亦兼容顶层 `block`）。"""

    model_config = ConfigDict(extra="forbid")

    systems: list[SystemNode] = Field(default_factory=list)
    blocks: list[BlockNode] = Field(default_factory=list)

from __future__ import annotations

from typing import Any


class SchemaErrorText:
    """用户配置校验报错文本的统一格式入口。"""

    @staticmethod
    def field(name: str) -> str:
        return f"'{name}'"

    @classmethod
    def fields(cls, *names: str) -> str:
        return " 或 ".join(cls.field(name) for name in names)

    @classmethod
    def node(cls, kind: str, name: str) -> str:
        return f"{kind} 节点 {name!r}"

    @classmethod
    def nodes_key(cls, key: Any) -> str:
        return f"{cls.field('nodes')}[{key!r}]"

    @classmethod
    def missing_field(cls, name: str) -> str:
        return f"须填写 {cls.field(name)}"

    @classmethod
    def unsupported_field(cls, kind: str, old: str, replacement: str) -> str:
        return (
            f"{kind} 节点不支持 {cls.field(old)} 字段，"
            f"请使用 {cls.field(replacement)}"
        )


ERR = SchemaErrorText()

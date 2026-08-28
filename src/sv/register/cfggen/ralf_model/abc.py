from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AbstractRalfField(Protocol):
    """RALF `field` 对应的对象应至少具备 `name`。"""

    name: str


@runtime_checkable
class AbstractRalfRegister(Protocol):
    """RALF `register` 对应的对象应至少具备 `name`。"""

    name: str


@runtime_checkable
class AbstractRalfBlock(Protocol):
    """RALF `block` 对应的对象应至少具备 `name`。"""

    name: str

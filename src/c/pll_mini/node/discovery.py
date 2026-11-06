from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from itertools import combinations
from pkgutil import iter_modules
from typing import Any

from pydantic import BaseModel

from .base import NodeBase


@dataclass(frozen=True)
class InputForm:
    """A plugin-owned spelling and optional discriminator of a node input."""

    kind: str
    field: str = ""
    values: tuple[str, ...] = ()
    default: str = ""
    defaults: tuple[tuple[str, str], ...] = ()
    target_kind: str = ""

    def normalize(self, item: dict[str, Any], canonical: str) -> dict | None:
        if item.get("kind") != self.kind:
            return None
        if self.field:
            value = item.get(self.field, self.default)
            if not isinstance(value, str) or value.strip().lower() not in self.values:
                return None
            return {
                **dict(self.defaults),
                **item,
                "kind": self.target_kind or canonical,
                self.field: value.strip().lower(),
            }
        return {**dict(self.defaults), **item, "kind": self.target_kind or canonical}


def discover(
    package: str,
) -> tuple[dict[str, type[NodeBase]], tuple[type[BaseModel], ...]]:
    """Discover local plugins; imports must not require a partially built registry."""
    namespace = import_module(package)
    plugins = {}
    settings = []
    for entry in sorted(iter_modules(namespace.__path__), key=lambda item: item.name):
        if entry.name.startswith("_"):
            continue
        module = import_module(f"{package}.{entry.name}")
        owned = [
            value
            for value in vars(module).values()
            if isinstance(value, type)
            and issubclass(value, NodeBase)
            and value is not NodeBase
            and value.__module__ == module.__name__
        ]
        if len(owned) != 1:
            raise ValueError(f"{module.__name__}: exactly one owned node is required")
        plugin = owned[0]
        kind = plugin.model_fields["kind"].default
        if kind != entry.name or kind in plugins:
            raise ValueError(
                f"{module.__name__}: missing or duplicate plugin kind {kind!r}"
            )
        plugins[kind] = plugin
        for schema in getattr(module, "SETTINGS", ()):
            if (
                not isinstance(schema, type)
                or not issubclass(schema, BaseModel)
                or schema.__module__ != module.__name__
            ):
                raise ValueError(
                    f"{module.__name__}: settings must be owned validation models"
                )
            duplicates = set(schema.model_fields).intersection(
                key for previous in settings for key in previous.model_fields
            )
            if duplicates:
                raise ValueError(
                    f"{module.__name__}: duplicate settings fields {sorted(duplicates)}"
                )
            settings.append(schema)
    forms = [
        (kind, form) for kind, plugin in plugins.items() for form in plugin.input_forms
    ]
    known = set(plugins) | {form.kind for _, form in forms}
    forwards = {}
    for owner, form in forms:
        if form.target_kind:
            if form.target_kind not in known:
                raise ValueError(f"{owner}: unknown alias target {form.target_kind!r}")
            forwards.setdefault(form.kind, set()).add(form.target_kind)

    def visit(kind, pending):
        if kind in pending:
            raise ValueError(f"plugin input alias cycle: {kind!r}")
        for target in forwards.get(kind, ()):
            visit(target, pending | {kind})

    for kind in forwards:
        visit(kind, set())
    for (left_kind, left), (right_kind, right) in combinations(forms, 2):
        if left.kind != right.kind:
            continue
        for left_value in left.values or ("",):
            for right_value in right.values or ("",):
                if (
                    left.field
                    and left.field == right.field
                    and left_value != right_value
                ):
                    continue
                witness = {"kind": left.kind}
                if left.field:
                    witness[left.field] = left_value
                if right.field:
                    witness[right.field] = right_value
                if (
                    left.normalize(witness, left_kind) is not None
                    and right.normalize(witness, right_kind) is not None
                ):
                    raise ValueError(
                        f"ambiguous input forms: {left_kind!r}, {right_kind!r}: {witness!r}"
                    )
    return plugins, tuple(settings)

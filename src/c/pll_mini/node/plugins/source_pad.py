from __future__ import annotations

from typing import Literal

from pydantic import Field

from .source import ClockSourceNode


class PadNode(ClockSourceNode):
    """Concrete source_pad node plugin."""

    kind: Literal["source_pad"] = "source_pad"
    source_kind: Literal["pad"] = Field(default="pad", description="Device variant")

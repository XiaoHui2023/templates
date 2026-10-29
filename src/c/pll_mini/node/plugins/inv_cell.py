from __future__ import annotations

from typing import Literal

from pydantic import Field

from .inv import InvNode


class InvCellNode(InvNode):
    """Concrete inv_cell node plugin."""

    kind: Literal["inv_cell"] = "inv_cell"
    inv_kind: Literal["inv_cell"] = Field(
        default="inv_cell", description="Device variant"
    )

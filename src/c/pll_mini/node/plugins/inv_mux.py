from __future__ import annotations

from typing import Literal

from pydantic import Field

from .inv import InvNode


class InvMuxNode(InvNode):
    """Concrete inv_mux node plugin."""

    kind: Literal["inv_mux"] = "inv_mux"
    inv_kind: Literal["inv_mux"] = Field(
        default="inv_mux", description="Device variant"
    )

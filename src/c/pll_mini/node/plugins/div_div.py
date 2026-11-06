from __future__ import annotations

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from node.ratio import QuotientNode


class DivDivNode(QuotientNode):
    minimum_ratio = 1
    maximum_ratio = 64
    configured_maximum = 64
    reg_keys = frozenset(("rst", "load", "div"))
    input_forms = (
        InputForm("div", "div_kind", ("div", "div_n"), "div"),
        InputForm("div_n", defaults=(("div_kind", "div_n"),), target_kind="div"),
    )
    """Concrete div_div node plugin."""

    kind: Literal["div_div"] = "div_div"
    div_kind: Literal["div", "div_n"] = Field(
        default="div", description="Device variant"
    )

    def control_encodings(self, builder):
        if self.ratio is not None or not self.regs:
            return {}
        ratio = builder.variable(self.name, "ratio")
        return {"div": (self.regs["div"], f"(- {ratio} 1)")}

    def control_domain(self, builder, role, encoding, maximum):
        if role == "div":
            return (
                "true"
                if maximum >= 63
                else f"(<= {builder.variable(self.name, 'ratio')} {maximum + 1})"
            )
        return super().control_domain(builder, role, encoding, maximum)

    def plan_patches(self, index, settings, resolved):
        from registers.plan import _patch

        if not self.regs:
            return []
        patches = [
            _patch(
                index,
                node_name=self.name,
                raw_path=self.regs["rst"],
                value=0 if settings.div_reg_high_means_reset else 1,
                note=f"{self.name} rst release",
            )
        ]
        value = max(0, resolved.ratio - 1)
        patches.append(
            _patch(
                index,
                node_name=self.name,
                raw_path=self.regs["div"],
                value=value,
                note=f"{self.name} ratio={resolved.ratio} div={value}",
            )
        )
        patches.append(
            _patch(
                index,
                node_name=self.name,
                raw_path=self.regs["load"],
                value=1,
                note=f"{self.name} load",
            )
        )
        return patches

    @field_validator("div_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("div", "div_n"), "div_kind")


class DivSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    div_reg_high_means_reset: bool = Field(
        False,
        description="为真时 div 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )


SETTINGS = (DivSettings,)

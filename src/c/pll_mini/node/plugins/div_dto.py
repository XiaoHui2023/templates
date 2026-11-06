from __future__ import annotations

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from node.ratio import QuotientNode


class DivDtoNode(QuotientNode):
    configured_maximum = 64
    reg_keys = frozenset(("rst", "load", "bypass", "step"))
    minimum_ratio = 2
    maximum_ratio = 1 << 25
    input_forms = (
        InputForm("div", "div_kind", ("dto", "dto_n")),
        InputForm("dto", defaults=(("div_kind", "dto"),), target_kind="div"),
        InputForm("dto_n", defaults=(("div_kind", "dto_n"),), target_kind="div"),
    )
    """Concrete div_dto node plugin."""

    kind: Literal["div_dto"] = "div_dto"
    div_kind: Literal["dto", "dto_n"] = Field(
        default="dto", description="Device variant"
    )

    def control_encodings(self, builder):
        if self.ratio is not None or not self.regs:
            return {}
        ratio = builder.variable(self.name, "ratio")
        return {"step": (self.regs["step"], f"(div {self.maximum_ratio} {ratio})")}

    def control_domain(self, builder, role, encoding, maximum):
        if role == "step":
            minimum = self.maximum_ratio // (maximum + 1) + 1
            return (
                "true"
                if minimum <= 2
                else f"(>= {builder.variable(self.name, 'ratio')} {minimum})"
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
                value=0 if settings.dto_reg_high_means_reset else 1,
                note=f"{self.name} rst release",
            )
        ]
        step = self.maximum_ratio // resolved.ratio
        note = f"{self.name} ratio={resolved.ratio} load=1 bypass=0 step={step}"
        for key, value in zip(("load", "bypass", "step"), (1, 0, step), strict=True):
            patches.append(
                _patch(
                    index,
                    node_name=self.name,
                    raw_path=self.regs[key],
                    value=value,
                    note=note if key == "load" else "",
                )
            )
        return patches

    @field_validator("div_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("dto", "dto_n"), "div_kind")


class DtoSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    dto_reg_high_means_reset: bool = Field(
        False,
        description="为真时 dto 的 rst 写 1 表示复位；为假时写 0 表示复位。",
    )


SETTINGS = (DtoSettings,)

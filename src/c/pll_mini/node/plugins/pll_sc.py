from __future__ import annotations

from functools import lru_cache

from model.arithmetic import freq_within_tolerance
from reg_paths import reg_key_to_c_ident
from registers.program import (
    WriteTemplate,
    keys_slot_specs,
    group_reg_write_templates,
)

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal
from load.regmodel import RegModelIndex

from pydantic import BaseModel, ConfigDict, Field, model_validator

from node.synthesis import SynthesizedNode


class PllScNode(SynthesizedNode):
    plan_group = "pll"
    program_variant = "sc"
    function_prefix = "pll_mini_config_pll_"
    configuration_key = "pll_cfg"
    ready_key = "lock"
    poll_function = "pll_mini_wait_lock"
    poll_parameter = "lock_mask"
    frequency_rule = "pll_freq"
    constraint_fields = {"pll_freq": ("freq",), "fixed_freq": ("freq",)}
    reg_keys = frozenset(
        (
            "bypass",
            "dsmpd",
            "fbdiv",
            "lock",
            "pd",
            "postdiv1",
            "postdiv2",
            "postdivpd",
            "refdiv",
            "vocpd",
        )
    )
    formula = "f_out = f_ref * fbdiv // (refdiv * postdiv1 * postdiv2)"
    input_forms = (InputForm("pll", "pll_kind", ("sc",)),)
    """Concrete pll_sc node plugin."""

    kind: Literal["pll_sc"] = "pll_sc"
    pll_kind: Literal["sc"] = Field(default="sc", description="Device variant")

    def search(self, ref, targets, settings, tolerance):
        lo, hi, den = tolerance
        return search_pll_sc(
            ref,
            targets[""],
            fbdiv_min=settings.pll_sc_fbdiv_min,
            fbdiv_max=settings.pll_sc_fbdiv_max,
            tol_lo=lo,
            tol_hi=hi,
            tol_den=den,
        )

    def configuration(self, vars_map):
        return {
            "vocpd": 0,
            "postdivpd": 0,
            "dsmpd": 0,
            "pd": 0,
            "bypass": 0,
            "refdiv": vars_map["refdiv"],
            "postdiv2": vars_map["postdiv2"],
            "postdiv1": vars_map["postdiv1"],
            "fbdiv": vars_map["fbdiv"],
        }

    def actual_frequency(self, ref, values, group):
        return pll_sc_actual_hz(
            ref,
            values.get("fbdiv", 0),
            values.get("refdiv", 0),
            values.get("postdiv1", 0),
            values.get("postdiv2", 0),
        )

    def slot_specs(self, index):
        return (
            *keys_slot_specs(PLL_SC_PD_KEYS, "sc_pd", self, index),
            *keys_slot_specs(PLL_SC_DIV_KEYS, "sc_div", self, index),
        )

    def configuration_keys(self, cfg_by_freq):
        keys = set().union(*(cfg.keys() for cfg in cfg_by_freq.values()))
        return tuple(key for key in PLL_SC_DIV_KEYS if key in keys)

    def write_templates(self, index):
        return _sc_write_templates(index, self)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("sc",), "pll_kind")


class PllScSettings(BaseModel):
    """Plugin-owned configuration defaults."""

    model_config = ConfigDict(extra="forbid")

    pll_sc_fbdiv_min: int = Field(
        16,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 下限。",
    )

    pll_sc_fbdiv_max: int = Field(
        84,
        ge=1,
        le=4095,
        description="允许 PLL SC FBDIV 上限。",
    )

    @model_validator(mode="after")
    def _validate_pll_sc_fbdiv_range(self) -> PllScSettings:
        if self.pll_sc_fbdiv_min > self.pll_sc_fbdiv_max:
            raise ValueError(
                f"pll_sc_fbdiv_min ({self.pll_sc_fbdiv_min}) 须不大于 "
                f"pll_sc_fbdiv_max ({self.pll_sc_fbdiv_max})"
            )
        return self


SETTINGS = (PllScSettings,)


@lru_cache(maxsize=4096)
def search_pll_sc(
    ref_hz: int,
    out_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    return _search_pll_sc_uncached(
        ref_hz,
        out_hz,
        fbdiv_min=fbdiv_min,
        fbdiv_max=fbdiv_max,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )


def _search_pll_sc_uncached(
    ref_hz: int,
    out_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0:
        return None
    best: tuple[int, dict[str, int]] | None = None
    for refdiv in range(1, 64):
        for postdiv1 in range(1, 8):
            for postdiv2 in range(1, 8):
                for fbdiv in range(fbdiv_min, fbdiv_max + 1):
                    actual = pll_sc_actual_hz(ref_hz, fbdiv, refdiv, postdiv1, postdiv2)
                    if freq_within_tolerance(
                        out_hz,
                        actual,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ):
                        coeffs = {
                            "fbdiv": fbdiv,
                            "refdiv": refdiv,
                            "postdiv1": postdiv1,
                            "postdiv2": postdiv2,
                        }
                        error = abs(actual - out_hz)
                        if error == 0:
                            return coeffs
                        if best is None or error < best[0]:
                            best = (error, coeffs)
    return best[1] if best is not None else None


def pll_sc_actual_hz(
    ref_hz: int,
    fbdiv: int,
    refdiv: int,
    postdiv1: int,
    postdiv2: int,
) -> int:
    product = refdiv * postdiv1 * postdiv2
    if ref_hz <= 0 or product < 1 or fbdiv < 1:
        return 0
    return (ref_hz * fbdiv) // product


PLL_SC_PD_KEYS = ("vocpd", "postdivpd", "dsmpd", "pd", "bypass")

PLL_SC_DIV_KEYS = ("refdiv", "postdiv2", "postdiv1", "fbdiv")


def _sc_write_templates(
    index: RegModelIndex,
    template_node: SynthesizedNode,
) -> tuple[WriteTemplate, ...]:
    pd_down = group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        slot_id="sc_pd",
        value_expr_for_key=lambda _key: "1",
        comment_for_key=lambda key: "power-down" if key == "vocpd" else key,
    )
    div_cfg = group_reg_write_templates(
        index,
        template_node,
        PLL_SC_DIV_KEYS,
        slot_id="sc_div",
        value_expr_for_key=reg_key_to_c_ident,
        comment_for_key=lambda key: key,
    )
    pd_en = group_reg_write_templates(
        index,
        template_node,
        PLL_SC_PD_KEYS,
        slot_id="sc_pd",
        value_expr_for_key=lambda _key: "0",
        comment_for_key=lambda key: "enable" if key == "vocpd" else key,
    )
    return pd_down + div_cfg + pd_en

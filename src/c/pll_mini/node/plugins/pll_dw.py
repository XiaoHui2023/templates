from __future__ import annotations

from functools import lru_cache

from model.arithmetic import freq_within_tolerance
from reg_paths import reg_key_to_c_ident
from registers.program import (
    WriteTemplate,
    WritePartTemplate,
    slot_param_name,
)

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal
from load.regmodel import RegModelIndex

from pydantic import Field

from node.synthesis import SynthesizedNode


class PllDwNode(SynthesizedNode):
    plan_group = "pll"
    program_variant = "dw"
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
            "divvcop",
            "divvcor",
            "enp",
            "enr",
            "fbdiv",
            "lock",
            "p",
            "prediv",
            "pwron",
            "r",
            "reset",
            "shift",
        )
    )
    formula = "f_out = f_ref * fbdiv // (p + 1)"
    input_forms = (InputForm("pll", "pll_kind", ("dw",)),)
    """Concrete pll_dw node plugin."""

    kind: Literal["pll_dw"] = "pll_dw"
    pll_kind: Literal["dw"] = Field(default="dw", description="Device variant")

    def search(self, ref, targets, settings, tolerance):
        lo, hi, den = tolerance
        return search_pll_dw(ref, targets[""], tol_lo=lo, tol_hi=hi, tol_den=den)

    def configuration(self, vars_map):
        return {
            "fbdiv": vars_map["fbdiv"],
            "prediv": 0,
            "reset": 0,
            "pwron": 1,
            "shift": 0,
            "bypass": 0,
            "divvcor": 0,
            "r": 4,
            "p": vars_map["p"],
            "divvcop": 0,
            "enr": 1,
            "enp": 1,
        }

    def actual_frequency(self, ref, values, group):
        return pll_dw_actual_hz(ref, values.get("fbdiv", 0), values.get("p", 0))

    def slot_specs(self, index):
        reg_paths_order: list[str] = []
        keys_by_reg: dict[str, list[str]] = {}
        for key in PLL_DW_ORDER:
            ref = index.resolve(
                self.regs[key], ctx=f"pll self {self.name!r} regs[{key!r}]"
            )
            reg_path = ref.reg.path
            if reg_path not in keys_by_reg:
                reg_paths_order.append(reg_path)
                keys_by_reg[reg_path] = []
            keys_by_reg[reg_path].append(key)
        return tuple(
            (
                (f"dw_{idx}", tuple(keys_by_reg[reg_path]))
                for idx, reg_path in enumerate(reg_paths_order)
            )
        )

    def configuration_keys(self, cfg_by_freq):
        keys = set().union(*(cfg.keys() for cfg in cfg_by_freq.values()))
        return tuple(key for key in PLL_DW_ORDER if key in keys)

    def write_templates(self, index):
        return _dw_write_templates(index, self)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("dw",), "pll_kind")


@lru_cache(maxsize=4096)
def search_pll_dw(
    ref_hz: int,
    out_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    return _search_pll_dw_uncached(
        ref_hz,
        out_hz,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )


def _search_pll_dw_uncached(
    ref_hz: int,
    out_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0:
        return None
    best: tuple[int, dict[str, int]] | None = None
    for p in range(0, 8):
        for fbdiv in range(DW_FBDIV_MIN, DW_FBDIV_MAX + 1):
            actual = pll_dw_actual_hz(ref_hz, fbdiv, p)
            if freq_within_tolerance(
                out_hz,
                actual,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            ):
                coeffs = {"fbdiv": fbdiv, "p": p}
                error = abs(actual - out_hz)
                if error == 0:
                    return coeffs
                if best is None or error < best[0]:
                    best = (error, coeffs)
    return best[1] if best is not None else None


def pll_dw_actual_hz(ref_hz: int, fbdiv: int, p: int) -> int:
    postdiv = p + 1
    if ref_hz <= 0 or fbdiv < 1 or postdiv < 1:
        return 0
    return (ref_hz * fbdiv) // postdiv


DW_FBDIV_MIN = 1
DW_FBDIV_MAX = 1023

PLL_DW_ORDER = (
    "fbdiv",
    "prediv",
    "reset",
    "pwron",
    "shift",
    "bypass",
    "divvcor",
    "r",
    "p",
    "divvcop",
    "enr",
    "enp",
)


def _dw_write_templates(
    index: RegModelIndex,
    template_node: SynthesizedNode,
) -> tuple[WriteTemplate, ...]:
    slot_specs = template_node.slot_specs(index)
    templates: list[WriteTemplate] = []
    for slot_id, keys in slot_specs:
        parts: list[WritePartTemplate] = []
        reg_path = ""
        for key in keys:
            ref = index.resolve(
                template_node.regs[key],
                ctx=f"pll node {template_node.name!r} regs[{key!r}]",
            )
            reg_path = ref.reg.path
            parts.append(
                WritePartTemplate(
                    ref.effective_lsb,
                    ref.effective_width,
                    reg_key_to_c_ident(key),
                    key,
                )
            )
        templates.append(
            WriteTemplate(
                slot_param_name(slot_id),
                tuple(parts),
                reg_path,
                slot_id,
            )
        )
    return tuple(templates)

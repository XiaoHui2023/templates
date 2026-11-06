from __future__ import annotations

from functools import lru_cache

from reg_paths import reg_key_to_c_ident
from registers.program import (
    WriteTemplate,
    WritePartTemplate,
    keys_slot_specs,
    unique_slot_specs_in_order,
    slot_id_for_reg_key,
    slot_param_name,
)

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal
from load.regmodel import RegModelIndex

from pydantic import Field

from node.synthesis import SynthesizedNode


class PllTciNode(SynthesizedNode):
    def frequency_matches(self, target, actual, tolerance):
        return target == actual

    plan_group = "pll"
    program_variant = "tci"
    function_prefix = "pll_mini_config_pll_"
    configuration_key = "pll_cfg"
    ready_key = "lock"
    poll_function = "pll_mini_wait_lock"
    poll_parameter = "lock_mask"
    frequency_rule = "pll_freq"
    constraint_fields = {"pll_freq": ("freq",), "fixed_freq": ("freq",)}
    reg_keys = frozenset(
        ("bwadj", "bypass", "clkf", "clkod", "clkr", "lock", "pwrdn", "reset")
    )
    formula = "f_out = f_ref * clkf"
    input_forms = (InputForm("pll", "pll_kind", ("tci",)),)
    """Concrete pll_tci node plugin."""

    kind: Literal["pll_tci"] = "pll_tci"
    pll_kind: Literal["tci"] = Field(default="tci", description="Device variant")

    def search(self, ref, targets, settings, tolerance):
        lo, hi, den = tolerance
        return search_pll_tci(
            ref,
            targets[""],
        )

    def configuration(self, vars_map):
        clkf = vars_map["clkf"]
        return tci_pll_cfg_from_clkf(clkf)

    def actual_frequency(self, ref, values, group):
        return pll_tci_actual_hz(ref, values.get("clkf", 0))

    def slot_specs(self, index):
        return (
            *keys_slot_specs(PLL_TCI_CTRL_KEYS, "tci_ctrl", self, index),
            *keys_slot_specs(PLL_TCI_DIV_KEYS, "tci_div", self, index),
        )

    def configuration_keys(self, cfg_by_freq):
        keys = set().union(*(cfg.keys() for cfg in cfg_by_freq.values()))
        return tuple(key for key in PLL_TCI_DIV_KEYS if key in keys)

    def write_templates(self, index):
        return _tci_write_templates(index, self)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("tci",), "pll_kind")


@lru_cache(maxsize=4096)
def search_pll_tci(
    ref_hz: int,
    out_hz: int,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0 or out_hz % ref_hz != 0:
        return None
    clkf = out_hz // ref_hz
    if clkf < 1:
        return None
    if pll_tci_actual_hz(ref_hz, clkf) != out_hz:
        return None
    return {"clkf": clkf}


def pll_tci_actual_hz(ref_hz: int, clkf: int) -> int:
    if ref_hz <= 0 or clkf < 1:
        return 0
    return ref_hz * clkf


def tci_pll_cfg_from_clkf(clkf: int) -> dict[str, int]:
    return {
        "clkr": 1,
        "clkf": clkf,
        "clkod": 1,
        "bwadj": clkf,
        "bypass": 0,
        "pwrdn": 0,
        "reset": 0,
    }


PLL_TCI_CTRL_KEYS = ("bypass", "pwrdn", "reset")

PLL_TCI_DIV_KEYS = ("clkod", "clkf", "clkr", "bwadj")


def _tci_write_templates(
    index: RegModelIndex,
    template_node: SynthesizedNode,
) -> tuple[WriteTemplate, ...]:
    slot_specs = unique_slot_specs_in_order(template_node.slot_specs(index))
    templates: list[WriteTemplate] = []

    def _append_field_write(key: str, value_expr: str, comment: str) -> None:
        sid = slot_id_for_reg_key(key, slot_specs)
        ref = index.resolve(
            template_node.regs[key],
            ctx=f"pll node {template_node.name!r} regs[{key!r}]",
        )
        templates.append(
            WriteTemplate(
                slot_param_name(sid),
                (
                    WritePartTemplate(
                        ref.effective_lsb,
                        ref.effective_width,
                        value_expr,
                        comment,
                    ),
                ),
                ref.reg.path,
                sid,
            )
        )

    for key, val in zip(PLL_TCI_CTRL_KEYS, (1, 0, 1), strict=True):
        comment = "bypass=1 pwrdn=0 reset=1" if key == "bypass" else key
        _append_field_write(key, str(val), comment)
    for key in PLL_TCI_DIV_KEYS:
        _append_field_write(key, reg_key_to_c_ident(key), key)
    _append_field_write("reset", "0", "reset release")
    _append_field_write("bypass", "0", "bypass off")
    return tuple(templates)

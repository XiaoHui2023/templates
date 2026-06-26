from __future__ import annotations

from formulas import tci_pll_cfg_from_clkf
from reg_paths import INNO_PLL_OUTPUT_GROUPS, inno_postdiv_reg_keys as _inno_keys

__all__ = ["pll_cfg_from_solved"]


def pll_cfg_from_solved(
    pll_kind: str,
    vars_map: dict[str, int],
    *,
    output_groups: list[str] | None = None,
) -> dict[str, int]:
    """由求解得到的 PLL 整数变量组装寄存器配置。"""
    if pll_kind == "tci":
        clkf = vars_map["clkf"]
        return tci_pll_cfg_from_clkf(clkf)
    if pll_kind == "sc":
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
    if pll_kind == "dw":
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
    if pll_kind == "inno":
        cfg: dict[str, int] = {
            "pd": 0,
            "refdiv": vars_map["refdiv"],
            "fbdiv": vars_map["fbdiv"],
        }
        groups = output_groups or list(INNO_PLL_OUTPUT_GROUPS)
        for group_id in groups:
            p1_key, p2_key = _inno_keys(group_id)
            cfg[p1_key] = vars_map[f"postdiv1_{group_id}"]
            cfg[p2_key] = vars_map[f"postdiv2_{group_id}"]
        return cfg
    raise ValueError(f"未知 pll_kind {pll_kind!r}")

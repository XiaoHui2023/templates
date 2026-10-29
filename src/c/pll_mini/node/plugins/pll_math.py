from __future__ import annotations

SC_FBDIV_HW_MIN = 1


SC_FBDIV_HW_MAX = 4095


DW_FBDIV_MIN = 1


DW_FBDIV_MAX = 1023


INNO_FBDIV_HW_MAX = 4095


def inno_fbdiv_legal(fbdiv: int) -> bool:
    if 0 <= fbdiv <= 7:
        return False
    if fbdiv == 11:
        return False
    return True


def pll_tci_actual_hz(ref_hz: int, clkf: int) -> int:
    if ref_hz <= 0 or clkf < 1:
        return 0
    return ref_hz * clkf


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


def pll_dw_actual_hz(ref_hz: int, fbdiv: int, p: int) -> int:
    postdiv = p + 1
    if ref_hz <= 0 or fbdiv < 1 or postdiv < 1:
        return 0
    return (ref_hz * fbdiv) // postdiv


def inno_postdiv_to_reg(postdiv: int) -> int:
    if postdiv < 1 or postdiv > 7:
        raise ValueError(f"inno postdiv {postdiv} 应在 1～7")
    return postdiv - 1


def inno_postdiv_from_reg(reg: int) -> int:
    return reg + 1


def pll_inno_actual_hz(
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

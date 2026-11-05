from __future__ import annotations

FREQ_TOL_DEN = 100


def freq_tolerance_bounds(
    period_tolerance: float,
) -> tuple[int, int, int]:
    tol_num = round(period_tolerance * FREQ_TOL_DEN)
    return FREQ_TOL_DEN - tol_num, FREQ_TOL_DEN + tol_num, FREQ_TOL_DEN


def freq_within_tolerance(
    out_hz: int,
    hw_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> bool:
    if out_hz <= 0 or hw_hz <= 0:
        return False
    return out_hz * tol_lo <= hw_hz * tol_den and out_hz * tol_hi >= hw_hz * tol_den


def div_hw_from_input(in_hz: int, ratio: int) -> tuple[int, int]:
    """整数分频：f_in = f_hw * ratio + rem，0 <= rem < ratio。"""
    if ratio < 1:
        raise ValueError(f"ratio {ratio} 须 >= 1")
    rem = in_hz % ratio
    freq_hw = in_hz // ratio
    if in_hz != freq_hw * ratio + rem:
        raise ValueError("div 余数分解失败")
    return freq_hw, rem

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


def div_ratio_reaches_output(
    in_hz: int,
    want_out_hz: int,
    ratio: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> bool:
    """给定输入频率与 ratio，是否存在 rem 使 want_out 在容差内接近 f_hw。"""
    if ratio < 1 or in_hz <= 0 or want_out_hz <= 0:
        return False
    freq_hw, _ = div_hw_from_input(in_hz, ratio)
    return freq_within_tolerance(
        want_out_hz,
        freq_hw,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )


def find_div_ratio(
    in_hz: int,
    want_out_hz: int,
    candidates: tuple[int, ...] | list[int],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> int | None:
    for ratio in candidates:
        if div_ratio_reaches_output(
            in_hz,
            want_out_hz,
            ratio,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            return ratio
    return None


def best_div_ratio(
    in_hz: int,
    want_out_hz: int,
    *,
    min_ratio: int,
    max_ratio: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> int | None:
    """Return the legal ratio with the smallest integer-divider frequency error."""
    if in_hz <= 0 or want_out_hz <= 0 or min_ratio < 1 or max_ratio < min_ratio:
        return None

    raw = in_hz // want_out_hz
    candidates = {
        min_ratio,
        max_ratio,
        raw - 1,
        raw,
        raw + 1,
        raw + 2,
    }
    best_ratio: int | None = None
    best_error: int | None = None
    for ratio in sorted(candidates):
        if ratio < min_ratio or ratio > max_ratio:
            continue
        freq_hw, _ = div_hw_from_input(in_hz, ratio)
        if not freq_within_tolerance(
            want_out_hz,
            freq_hw,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            continue
        error = abs(freq_hw - want_out_hz)
        if best_error is None or error < best_error:
            best_error = error
            best_ratio = ratio
    return best_ratio

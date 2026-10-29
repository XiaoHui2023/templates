from __future__ import annotations

from model.arithmetic import div_ratio_reaches_output, freq_within_tolerance

DTO_MAX_RATIO = 1 << 25


def dto_ratio_candidates_for_pair(
    in_hz: int,
    want_out_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> tuple[int, ...]:
    """从 f_in 与目标 f_out 反推 dto 合法 ratio 候选，避免扫全 2^25。"""
    if in_hz <= 0 or want_out_hz <= 0:
        return ()
    found: list[int] = []
    hw_min = max(1, (want_out_hz * tol_lo + tol_den - 1) // tol_den)
    hw_max = (want_out_hz * tol_hi) // tol_den
    for freq_hw in range(hw_min, hw_max + 1):
        if not freq_within_tolerance(
            want_out_hz,
            freq_hw,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            continue
        ratio = in_hz // freq_hw
        if ratio < 2 or ratio > DTO_MAX_RATIO:
            continue
        if div_ratio_reaches_output(
            in_hz,
            want_out_hz,
            ratio,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            found.append(ratio)
    return tuple(dict.fromkeys(found))


def div_ratio_to_n(ratio: int) -> int:
    if ratio <= 1:
        return 0
    if ratio > 64:
        raise ValueError(f"div ratio {ratio} 超过上限 64")
    return ratio - 1


def dto_ratio_to_step(ratio: int) -> int:
    if ratio <= 0:
        raise ValueError(f"dto ratio {ratio} 须为正")
    max_step = DTO_MAX_RATIO
    step = max_step // ratio
    if step < 1 or step >= max_step:
        raise ValueError(f"dto ratio {ratio} 对应 step {step} 不在 1～2^25-1")
    return step

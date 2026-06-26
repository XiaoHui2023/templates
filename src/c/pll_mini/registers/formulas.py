from __future__ import annotations

SC_FBDIV_HW_MIN = 1
SC_FBDIV_HW_MAX = 4095
DW_FBDIV_MIN = 1
DW_FBDIV_MAX = 1023
INNO_FBDIV_SCALE = 4
INNO_FBDIV_HW_MAX = 4095
DTO_MAX_RATIO = 1 << 25
FREQ_TOL_DEN = 100

CPU_GATE_RATIOS = frozenset({2, 3, 4, 6})


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
    for rem in range(ratio):
        hw_num = in_hz - rem
        if hw_num <= 0 or hw_num % ratio != 0:
            continue
        freq_hw = hw_num // ratio
        if freq_within_tolerance(
            want_out_hz,
            freq_hw,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        ):
            return True
    return False


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
        for rem in range(min(freq_hw, DTO_MAX_RATIO)):
            num = in_hz - rem
            if num <= 0 or num % freq_hw != 0:
                continue
            ratio = num // freq_hw
            if ratio < 2 or ratio > DTO_MAX_RATIO or num != freq_hw * ratio:
                continue
            if rem >= ratio:
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


def inno_fbdiv_legal(fbdiv: int) -> bool:
    if 0 <= fbdiv <= 7:
        return False
    if fbdiv == 11:
        return False
    return True


def cpu_gate_ratio_to_n(ratio: int) -> int:
    mapping = {2: 0x0, 3: 0x2, 4: 0x4, 6: 0x8}
    if ratio not in CPU_GATE_RATIOS:
        allowed = "、".join(str(r) for r in sorted(CPU_GATE_RATIOS))
        raise ValueError(f"cpu_gate ratio {ratio} 只能是 {allowed}")
    return mapping[ratio]


def cpu_gate_n_to_ratio(n: int) -> int:
    n &= 0xF
    if n in (0x0, 0x1):
        return 2
    if (n >> 2) == 0 and (n & 0x2):
        return 3
    if not (n & 0x8) and (n & 0x4):
        return 4
    if n & 0x8:
        return 6
    raise ValueError(f"cpu_gate div 0x{n:x} 无法反算合法 ratio")


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
        raise ValueError(
            f"dto ratio {ratio} 对应 step {step} 不在 1～2^25-1"
        )
    return step


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


def pll_inno_actual_hz(
    ref_hz: int,
    fbdiv: int,
    refdiv: int,
    postdiv1: int,
    postdiv2: int,
) -> int:
    product = INNO_FBDIV_SCALE * refdiv * postdiv1 * postdiv2
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


def inno_postdiv_reg_keys(group_id: str) -> tuple[str, str]:
    from reg_paths import inno_postdiv_reg_keys as _keys

    return _keys(group_id)

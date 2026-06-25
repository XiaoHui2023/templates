from __future__ import annotations

SC_FBDIV_HW_MIN = 1
SC_FBDIV_HW_MAX = 4095
DW_FBDIV_MIN = 1
DW_FBDIV_MAX = 1023
INNO_FBDIV_SCALE = 4
INNO_FBDIV_HW_MAX = 4095
DTO_MAX_RATIO = 1 << 25


def inno_fbdiv_legal(fbdiv: int) -> bool:
    if 0 <= fbdiv <= 7:
        return False
    if fbdiv == 11:
        return False
    return True


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


def div_ratio_from_freq(in_hz: int, out_hz: int) -> int:
    if in_hz <= 0 or out_hz <= 0:
        raise ValueError("div 前后级频率须为正")
    if in_hz % out_hz != 0:
        raise ValueError(
            f"div 无法由 {in_hz} Hz 整除得到 {out_hz} Hz"
        )
    ratio = in_hz // out_hz
    if ratio < 1 or ratio > 64:
        raise ValueError(f"div ratio {ratio} 须在 1～64")
    return ratio


def dto_ratio_from_freq(in_hz: int, out_hz: int) -> int:
    if in_hz <= 0 or out_hz <= 0:
        raise ValueError("dto 前后级频率须为正")
    if in_hz % out_hz != 0:
        raise ValueError(
            f"dto 无法由 {in_hz} Hz 整除得到 {out_hz} Hz"
        )
    ratio = in_hz // out_hz
    if ratio <= 1:
        raise ValueError("dto ratio 须大于 1")
    if ratio > DTO_MAX_RATIO:
        raise ValueError(f"dto ratio {ratio} 超过 2^25")
    dto_ratio_to_step(ratio)
    return ratio


def tci_divisors(out_hz: int, ref_hz: int) -> dict[str, int]:
    clkr = 1
    clkod = 1
    clkf = out_hz // ref_hz if ref_hz > 0 and out_hz > 0 else 1
    return {
        "clkr": clkr,
        "clkf": clkf,
        "clkod": clkod,
        "bwadj": clkf,
        "bypass": 0,
        "pwrdn": 0,
        "reset": 0,
    }


def sc_divisors(
    out_hz: int,
    ref_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
) -> tuple[int, int, int, int]:
    if ref_hz <= 0 or out_hz <= 0:
        return 1, 2, 1, 1

    def search(pref_only: bool) -> tuple[int, int, int, int] | None:
        best: tuple[int, int, int, int, int] | None = None
        for refdiv in range(1, 64):
            for postdiv1 in range(1, 8):
                for postdiv2 in range(1, 8):
                    product = refdiv * postdiv1 * postdiv2
                    fbdiv_r = out_hz * product / ref_hz
                    fbdiv_i = int(round(fbdiv_r))
                    if fbdiv_i < SC_FBDIV_HW_MIN or fbdiv_i > SC_FBDIV_HW_MAX:
                        continue
                    if pref_only and (
                        fbdiv_i < fbdiv_min or fbdiv_i > fbdiv_max
                    ):
                        continue
                    actual_hz = (ref_hz * fbdiv_i) // product
                    err = abs(out_hz - actual_hz)
                    if best is None or err < best[4]:
                        best = (fbdiv_i, refdiv, postdiv1, postdiv2, err)
        if best is None:
            return None
        return best[0], best[1], best[2], best[3]

    picked = search(True)
    if picked is None:
        picked = search(False)
    if picked is None:
        return 1, 2, 1, 1
    fbdiv, refdiv, postdiv1, postdiv2 = picked
    if fbdiv < fbdiv_min or fbdiv > fbdiv_max:
        raise ValueError(
            f"pll_sc fbdiv {fbdiv} 不在优先区间 [{fbdiv_min}:{fbdiv_max}]，"
            f"out {out_hz} Hz ref {ref_hz} Hz"
        )
    return fbdiv, refdiv, postdiv1, postdiv2


def sc_pll_cfg(
    out_hz: int,
    ref_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
) -> dict[str, int]:
    fbdiv, refdiv, postdiv1, postdiv2 = sc_divisors(
        out_hz, ref_hz, fbdiv_min=fbdiv_min, fbdiv_max=fbdiv_max
    )
    return {
        "vocpd": 0,
        "postdivpd": 0,
        "dsmpd": 0,
        "pd": 0,
        "bypass": 0,
        "refdiv": refdiv,
        "postdiv2": postdiv2,
        "postdiv1": postdiv1,
        "fbdiv": fbdiv,
    }


def dw_divisors(out_hz: int, ref_hz: int) -> tuple[int, int]:
    if ref_hz <= 0 or out_hz <= 0:
        return 1, 0
    best: tuple[int, int, int] | None = None
    for p in range(8):
        fbdiv_r = out_hz * (p + 1) / ref_hz
        fbdiv_i = int(round(fbdiv_r))
        if fbdiv_i < DW_FBDIV_MIN or fbdiv_i > DW_FBDIV_MAX:
            continue
        actual_hz = (ref_hz * fbdiv_i) // (p + 1)
        err = abs(out_hz - actual_hz)
        if best is None or err < best[2]:
            best = (fbdiv_i, p, err)
    if best is None:
        return 1, 0
    return best[0], best[1]


def dw_pll_cfg(out_hz: int, ref_hz: int) -> dict[str, int]:
    fbdiv, p = dw_divisors(out_hz, ref_hz)
    return {
        "fbdiv": fbdiv,
        "prediv": 0,
        "reset": 0,
        "pwron": 1,
        "shift": 0,
        "bypass": 0,
        "divvcor": 0,
        "r": 4,
        "p": p,
        "divvcop": 0,
        "enr": 1,
        "enp": 1,
    }


def inno_shared_divisors(
    out_hz: int,
    ref_hz: int,
    *,
    fbdiv_max: int = INNO_FBDIV_HW_MAX,
) -> tuple[int, int]:
    if ref_hz <= 0 or out_hz <= 0:
        return 1, 1
    best: tuple[int, int, int] | None = None
    for refdiv in range(1, 64):
        fbdiv_r = out_hz * refdiv * INNO_FBDIV_SCALE / ref_hz
        fbdiv_i = int(round(fbdiv_r))
        if fbdiv_i < 1 or fbdiv_i > fbdiv_max:
            continue
        if not inno_fbdiv_legal(fbdiv_i):
            continue
        actual_hz = (ref_hz * fbdiv_i) // (INNO_FBDIV_SCALE * refdiv)
        err = abs(out_hz - actual_hz)
        if best is None or err < best[2]:
            best = (fbdiv_i, refdiv, err)
    if best is None:
        return 1, 1
    return best[0], best[1]


def inno_postdivisors(
    out_hz: int,
    ref_hz: int,
    fbdiv: int,
    refdiv: int,
) -> tuple[int, int]:
    if ref_hz <= 0 or out_hz <= 0 or fbdiv < 1 or refdiv < 1:
        return 1, 1
    best: tuple[int, int, int] | None = None
    for postdiv1 in range(1, 8):
        for postdiv2 in range(1, 8):
            product = refdiv * postdiv1 * postdiv2
            if product < 1:
                continue
            actual_hz = (ref_hz * fbdiv) // (INNO_FBDIV_SCALE * product)
            err = abs(out_hz - actual_hz)
            if best is None or err < best[2]:
                best = (postdiv1, postdiv2, err)
    if best is None:
        return 1, 1
    return best[0], best[1]


def inno_pll_cfg(
    out_hz: int,
    ref_hz: int,
    *,
    output_groups: list[str] | None = None,
    fbdiv_max: int = INNO_FBDIV_HW_MAX,
) -> dict[str, int]:
    from reg_paths import INNO_PLL_OUTPUT_GROUPS, inno_postdiv_reg_keys

    fbdiv, refdiv = inno_shared_divisors(out_hz, ref_hz, fbdiv_max=fbdiv_max)
    postdiv1, postdiv2 = inno_postdivisors(out_hz, ref_hz, fbdiv, refdiv)
    cfg: dict[str, int] = {
        "pd": 0,
        "refdiv": refdiv,
        "fbdiv": fbdiv,
    }
    groups = output_groups or list(INNO_PLL_OUTPUT_GROUPS)
    for group_id in groups:
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        cfg[p1_key] = postdiv1
        cfg[p2_key] = postdiv2
    return cfg

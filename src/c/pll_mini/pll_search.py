from __future__ import annotations

from formulas import (
    DW_FBDIV_MAX,
    DW_FBDIV_MIN,
    freq_within_tolerance,
    inno_fbdiv_legal,
    pll_dw_actual_hz,
    pll_inno_actual_hz,
    pll_sc_actual_hz,
    pll_tci_actual_hz,
)


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
    if ref_hz <= 0 or out_hz <= 0:
        return None
    for refdiv in range(1, 64):
        for postdiv1 in range(1, 8):
            for postdiv2 in range(1, 8):
                product = refdiv * postdiv1 * postdiv2
                for fbdiv in range(fbdiv_min, fbdiv_max + 1):
                    actual = pll_sc_actual_hz(
                        ref_hz, fbdiv, refdiv, postdiv1, postdiv2
                    )
                    if freq_within_tolerance(
                        out_hz,
                        actual,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ):
                        return {
                            "fbdiv": fbdiv,
                            "refdiv": refdiv,
                            "postdiv1": postdiv1,
                            "postdiv2": postdiv2,
                        }
    return None


def search_pll_dw(
    ref_hz: int,
    out_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0:
        return None
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
                return {"fbdiv": fbdiv, "p": p}
    return None


def search_pll_inno(
    ref_hz: int,
    group_out_hz: dict[str, int],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[str, int] | None:
    if ref_hz <= 0:
        return None
    active_groups = {
        group: hz for group, hz in group_out_hz.items() if hz > 0
    }
    if not active_groups:
        return None
    for refdiv in range(1, 64):
        for fbdiv in range(1, 4096):
            if not inno_fbdiv_legal(fbdiv):
                continue
            vars_map: dict[str, int] = {
                "refdiv": refdiv,
                "fbdiv": fbdiv,
            }
            ok = True
            for group_id, target_hz in active_groups.items():
                matched = False
                for postdiv1 in range(1, 8):
                    for postdiv2 in range(1, 8):
                        actual = pll_inno_actual_hz(
                            ref_hz,
                            fbdiv,
                            refdiv,
                            postdiv1,
                            postdiv2,
                        )
                        if freq_within_tolerance(
                            target_hz,
                            actual,
                            tol_lo=tol_lo,
                            tol_hi=tol_hi,
                            tol_den=tol_den,
                        ):
                            vars_map[f"postdiv1_{group_id}"] = postdiv1
                            vars_map[f"postdiv2_{group_id}"] = postdiv2
                            matched = True
                            break
                    if matched:
                        break
                if not matched:
                    ok = False
                    break
            if ok:
                return vars_map
    return None


def search_pll_coefficients(
    pll_kind: str,
    ref_hz: int,
    out_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    group_out_hz: dict[str, int] | None = None,
) -> dict[str, int] | None:
    if pll_kind == "tci":
        return search_pll_tci(ref_hz, out_hz)
    if pll_kind == "sc":
        return search_pll_sc(
            ref_hz,
            out_hz,
            fbdiv_min=fbdiv_min,
            fbdiv_max=fbdiv_max,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
    if pll_kind == "dw":
        return search_pll_dw(
            ref_hz,
            out_hz,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
    if pll_kind == "inno":
        targets = group_out_hz or {}
        if not targets and out_hz > 0:
            targets = {"0": out_hz}
        return search_pll_inno(
            ref_hz,
            targets,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
    raise ValueError(f"未知 pll_kind {pll_kind!r}")

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from .formulas import (
    DW_FBDIV_MAX,
    DW_FBDIV_MIN,
    freq_within_tolerance,
    inno_fbdiv_legal,
    pll_dw_actual_hz,
    pll_inno_actual_hz,
    pll_sc_actual_hz,
    pll_tci_actual_hz,
)

ProgressHook = Callable[[int, int, str], None]


def _emit_progress(
    hook: ProgressHook | None,
    current: int,
    total: int,
    detail: str,
) -> None:
    if hook is None:
        return
    hook(current, total, detail)


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


@lru_cache(maxsize=4096)
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
    return _search_pll_sc_uncached(
        ref_hz,
        out_hz,
        fbdiv_min=fbdiv_min,
        fbdiv_max=fbdiv_max,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )


def _search_pll_sc_uncached(
    ref_hz: int,
    out_hz: int,
    *,
    fbdiv_min: int,
    fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
    progress: ProgressHook | None = None,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0:
        return None
    fbdiv_count = max(0, fbdiv_max - fbdiv_min + 1)
    total = 63 * 7 * 7 * max(1, fbdiv_count)
    current = 0
    for refdiv in range(1, 64):
        for postdiv1 in range(1, 8):
            for postdiv2 in range(1, 8):
                product = refdiv * postdiv1 * postdiv2
                for fbdiv in range(fbdiv_min, fbdiv_max + 1):
                    current += 1
                    if current == 1 or current % 4096 == 0:
                        _emit_progress(
                            progress,
                            current,
                            total,
                            f"refdiv={refdiv} postdiv={postdiv1}/{postdiv2}",
                        )
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
    progress: ProgressHook | None = None,
) -> dict[str, int] | None:
    if ref_hz <= 0 or out_hz <= 0:
        return None
    total = 8 * (DW_FBDIV_MAX - DW_FBDIV_MIN + 1)
    current = 0
    for p in range(0, 8):
        for fbdiv in range(DW_FBDIV_MIN, DW_FBDIV_MAX + 1):
            current += 1
            if current == 1 or current % 1024 == 0:
                _emit_progress(progress, current, total, f"p={p}")
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
    progress: ProgressHook | None = None,
) -> dict[str, int] | None:
    if ref_hz <= 0:
        return None
    active_groups = {
        group: hz for group, hz in group_out_hz.items() if hz > 0
    }
    if not active_groups:
        return None
    total = 63 * 4095
    current = 0
    for refdiv in range(1, 64):
        for fbdiv in range(1, 4096):
            current += 1
            if current == 1 or current % 4096 == 0:
                _emit_progress(progress, current, total, f"refdiv={refdiv}")
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
                for group_id in group_out_hz:
                    p1_key = f"postdiv1_{group_id}"
                    p2_key = f"postdiv2_{group_id}"
                    if p1_key not in vars_map:
                        vars_map[p1_key] = 1
                        vars_map[p2_key] = 1
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
    progress: ProgressHook | None = None,
) -> dict[str, int] | None:
    if pll_kind == "tci":
        return search_pll_tci(ref_hz, out_hz)
    if pll_kind == "sc":
        if progress is not None:
            return _search_pll_sc_uncached(
                ref_hz,
                out_hz,
                fbdiv_min=fbdiv_min,
                fbdiv_max=fbdiv_max,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
                progress=progress,
            )
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
        if progress is not None:
            return _search_pll_dw_uncached(
                ref_hz,
                out_hz,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
                progress=progress,
            )
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
            progress=progress,
        )
    raise ValueError(f"未知 pll_kind {pll_kind!r}")


def pll_ref_hz_candidates(
    pll_kind: str,
    *,
    out_hz: int = 0,
    group_out_hz: dict[str, int] | None = None,
    fbdiv_min: int,
    fbdiv_max: int,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> tuple[int, ...]:
    """从 PLL 输出频率反推可接受的参考频率候选，供 ref path dto 反推 ratio。"""
    if pll_kind == "tci":
        if out_hz <= 0:
            return ()
        found: dict[int, None] = {}
        for ref_hz in range(1, out_hz + 1):
            if out_hz % ref_hz != 0:
                continue
            if search_pll_tci(ref_hz, out_hz) is not None:
                found[ref_hz] = None
        return tuple(found.keys())
    if pll_kind == "sc":
        if out_hz <= 0:
            return ()
        found: dict[int, None] = {}
        for refdiv in range(1, 64):
            for postdiv1 in range(1, 8):
                for postdiv2 in range(1, 8):
                    for fbdiv in range(fbdiv_min, fbdiv_max + 1):
                        actual = pll_sc_actual_hz(
                            1, fbdiv, refdiv, postdiv1, postdiv2
                        )
                        if actual <= 0:
                            continue
                        num = out_hz * refdiv * postdiv1 * postdiv2
                        ref_nom = num // fbdiv
                        for ref_hz in (
                            max(1, ref_nom - 1),
                            ref_nom,
                            ref_nom + 1,
                        ):
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
                                found[ref_hz] = None
        return tuple(sorted(found.keys()))
    if pll_kind == "dw":
        if out_hz <= 0:
            return ()
        found = {}
        for p in range(0, 8):
            for fbdiv in range(DW_FBDIV_MIN, DW_FBDIV_MAX + 1):
                num = out_hz * (1 << p)
                ref_nom = num // fbdiv
                for ref_hz in (
                    max(1, ref_nom - 1),
                    ref_nom,
                    ref_nom + 1,
                ):
                    actual = pll_dw_actual_hz(ref_hz, fbdiv, p)
                    if freq_within_tolerance(
                        out_hz,
                        actual,
                        tol_lo=tol_lo,
                        tol_hi=tol_hi,
                        tol_den=tol_den,
                    ):
                        found[ref_hz] = None
        return tuple(sorted(found.keys()))
    if pll_kind == "inno":
        targets = {
            group: hz
            for group, hz in (group_out_hz or {}).items()
            if hz > 0
        }
        if not targets and out_hz > 0:
            targets = {"0": out_hz}
        if not targets:
            return ()
        found = {}
        for refdiv in range(1, 64):
            for fbdiv in range(1, 4096):
                if not inno_fbdiv_legal(fbdiv):
                    continue
                for postdiv1 in range(1, 8):
                    for postdiv2 in range(1, 8):
                        scale = refdiv * postdiv1 * postdiv2
                        for target_hz in targets.values():
                            num = target_hz * scale
                            ref_nom = num // fbdiv
                            for ref_hz in (
                                max(1, ref_nom - 1),
                                ref_nom,
                                ref_nom + 1,
                            ):
                                actual = pll_inno_actual_hz(
                                    ref_hz,
                                    fbdiv,
                                    refdiv,
                                    postdiv1,
                                    postdiv2,
                                )
                                if not freq_within_tolerance(
                                    target_hz,
                                    actual,
                                    tol_lo=tol_lo,
                                    tol_hi=tol_hi,
                                    tol_den=tol_den,
                                ):
                                    continue
                                if search_pll_inno(
                                    ref_hz,
                                    targets,
                                    tol_lo=tol_lo,
                                    tol_hi=tol_hi,
                                    tol_den=tol_den,
                                ):
                                    found[ref_hz] = None
        return tuple(sorted(found.keys()))
    return ()

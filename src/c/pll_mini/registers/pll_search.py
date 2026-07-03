from __future__ import annotations

from dataclasses import dataclass
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
POSTDIV_PAIRS = tuple(
    (postdiv1, postdiv2)
    for postdiv1 in range(1, 8)
    for postdiv2 in range(1, 8)
)


@dataclass(frozen=True)
class PllCandidateError:
    group: str
    target_hz: int
    actual_hz: int
    refdiv: int
    fbdiv: int
    postdiv1: int
    postdiv2: int

    @property
    def abs_error_hz(self) -> int:
        return abs(self.actual_hz - self.target_hz)

    @property
    def ppm_error(self) -> float:
        if self.target_hz <= 0:
            return 0.0
        return self.abs_error_hz * 1_000_000 / self.target_hz


@dataclass(frozen=True)
class PllSearchDiagnosis:
    pll_kind: str
    ref_hz: int
    targets: dict[str, int]
    reason: str
    best_shared: tuple[PllCandidateError, ...] = ()
    missing_single_groups: tuple[str, ...] = ()

    def format(self) -> str:
        lines = [
            f"原因：{self.reason}",
            f"参考频率 ref_hz={_fmt_hz(self.ref_hz)}",
        ]
        if self.targets:
            target_text = ", ".join(
                f"{group}={_fmt_hz(hz)}" for group, hz in self.targets.items()
            )
            lines.append(f"目标端口：{target_text}")
        if self.missing_single_groups:
            lines.append(
                "单输出也无合法候选的端口："
                + ", ".join(self.missing_single_groups)
            )
        if self.best_shared:
            first = self.best_shared[0]
            lines.append(
                "最接近的共用候选："
                f"refdiv={first.refdiv}, fbdiv={first.fbdiv}"
            )
            for item in self.best_shared:
                lines.append(
                    "  "
                    f"[{item.group}] target={_fmt_hz(item.target_hz)}, "
                    f"actual={_fmt_hz(item.actual_hz)}, "
                    f"postdiv={item.postdiv1}/{item.postdiv2}, "
                    f"error={item.abs_error_hz} Hz ({item.ppm_error:.3f} ppm)"
                )
        return "\n".join(lines)


def _emit_progress(
    hook: ProgressHook | None,
    current: int,
    total: int,
    detail: str,
) -> None:
    if hook is None:
        return
    hook(current, total, detail)


def _fmt_hz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz ({hz} Hz)"
    if hz % 1_000 == 0:
        return f"{hz // 1_000} kHz ({hz} Hz)"
    return f"{hz} Hz"


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


def diagnose_pll_coefficients(
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
) -> PllSearchDiagnosis:
    if pll_kind == "inno":
        targets = group_out_hz or {}
        if not targets and out_hz > 0:
            targets = {"0": out_hz}
        return _diagnose_pll_inno(
            ref_hz,
            targets,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
    targets = {"out": out_hz} if out_hz > 0 else {}
    return PllSearchDiagnosis(
        pll_kind=pll_kind,
        ref_hz=ref_hz,
        targets=targets,
        reason=(
            f"{pll_kind} 在当前合法系数范围内找不到满足容差的组合"
            f"（SC fbdiv 范围 {fbdiv_min}..{fbdiv_max}）"
        ),
    )


def _diagnose_pll_inno(
    ref_hz: int,
    group_out_hz: dict[str, int],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> PllSearchDiagnosis:
    active_groups = {
        group: hz for group, hz in group_out_hz.items() if hz > 0
    }
    if ref_hz <= 0:
        return PllSearchDiagnosis(
            pll_kind="inno",
            ref_hz=ref_hz,
            targets=active_groups,
            reason="参考频率无效，无法反推 INNO 系数",
        )
    if not active_groups:
        return PllSearchDiagnosis(
            pll_kind="inno",
            ref_hz=ref_hz,
            targets=active_groups,
            reason=(
                "没有有效的 INNO 输出端口目标频率；inno PLL 节点必须通过"
                "freq dict 指定各输出端口频率，或用整数 freq 指定所有端口同频"
            ),
        )

    group_candidates: dict[str, dict[tuple[int, int], PllCandidateError]] = {}
    for group_id, target_hz in active_groups.items():
        group_candidates[group_id] = _inno_group_candidates(
            ref_hz,
            group_id,
            target_hz,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )

    missing = tuple(
        group for group, candidates in group_candidates.items() if not candidates
    )
    candidate_keys: set[tuple[int, int]] = set()
    for candidates in group_candidates.values():
        candidate_keys.update(candidates)
    best_shared = _inno_best_shared_candidate(
        ref_hz,
        active_groups,
        candidate_keys,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    if missing:
        reason = "至少一个输出端口即使单独搜索也没有合法 INNO 候选"
    else:
        reason = (
            "各输出端口单独存在合法候选，但找不到同一组 refdiv/fbdiv"
            " 同时满足所有端口；INNO 两路输出只能分别调整 postdiv1/postdiv2"
        )
    return PllSearchDiagnosis(
        pll_kind="inno",
        ref_hz=ref_hz,
        targets=active_groups,
        reason=reason,
        best_shared=best_shared,
        missing_single_groups=missing,
    )


def _inno_group_candidates(
    ref_hz: int,
    group_id: str,
    target_hz: int,
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> dict[tuple[int, int], PllCandidateError]:
    candidates: dict[tuple[int, int], PllCandidateError] = {}
    hw_min = max(1, (target_hz * tol_lo + tol_den - 1) // tol_den)
    hw_max = (target_hz * tol_hi) // tol_den
    for refdiv in range(1, 64):
        for postdiv1, postdiv2 in POSTDIV_PAIRS:
            denom = refdiv * postdiv1 * postdiv2
            fbdiv_min = (hw_min * denom + ref_hz - 1) // ref_hz
            fbdiv_max = ((hw_max + 1) * denom - 1) // ref_hz
            for fbdiv in range(max(1, fbdiv_min), min(4095, fbdiv_max) + 1):
                if not inno_fbdiv_legal(fbdiv):
                    continue
                actual = pll_inno_actual_hz(
                    ref_hz, fbdiv, refdiv, postdiv1, postdiv2
                )
                if not freq_within_tolerance(
                    target_hz,
                    actual,
                    tol_lo=tol_lo,
                    tol_hi=tol_hi,
                    tol_den=tol_den,
                ):
                    continue
                key = (refdiv, fbdiv)
                item = PllCandidateError(
                    group=group_id,
                    target_hz=target_hz,
                    actual_hz=actual,
                    refdiv=refdiv,
                    fbdiv=fbdiv,
                    postdiv1=postdiv1,
                    postdiv2=postdiv2,
                )
                old = candidates.get(key)
                if old is None or item.abs_error_hz < old.abs_error_hz:
                    candidates[key] = item
    return candidates


def _inno_best_shared_candidate(
    ref_hz: int,
    active_groups: dict[str, int],
    candidate_keys: set[tuple[int, int]],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> tuple[PllCandidateError, ...]:
    best_items: tuple[PllCandidateError, ...] = ()
    best_score: tuple[int, int] | None = None
    for refdiv, fbdiv in candidate_keys:
        items: list[PllCandidateError] = []
        misses = 0
        error_sum = 0
        for group_id, target_hz in active_groups.items():
            item = _inno_best_group_for_shared(
                ref_hz, group_id, target_hz, refdiv, fbdiv
            )
            if not freq_within_tolerance(
                target_hz,
                item.actual_hz,
                tol_lo=tol_lo,
                tol_hi=tol_hi,
                tol_den=tol_den,
            ):
                misses += 1
            error_sum += item.abs_error_hz
            items.append(item)
        score = (misses, error_sum)
        if best_score is None or score < best_score:
            best_score = score
            best_items = tuple(items)
    return best_items


def _inno_best_group_for_shared(
    ref_hz: int,
    group_id: str,
    target_hz: int,
    refdiv: int,
    fbdiv: int,
) -> PllCandidateError:
    best: PllCandidateError | None = None
    for postdiv1, postdiv2 in POSTDIV_PAIRS:
        actual = pll_inno_actual_hz(ref_hz, fbdiv, refdiv, postdiv1, postdiv2)
        item = PllCandidateError(
            group=group_id,
            target_hz=target_hz,
            actual_hz=actual,
            refdiv=refdiv,
            fbdiv=fbdiv,
            postdiv1=postdiv1,
            postdiv2=postdiv2,
        )
        if best is None or item.abs_error_hz < best.abs_error_hz:
            best = item
    if best is None:
        raise RuntimeError("INNO postdiv candidates are empty")
    return best


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

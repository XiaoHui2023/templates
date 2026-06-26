from __future__ import annotations

import re
from typing import Dict, List, Tuple

_SMT_SAFE = re.compile(r"[^a-zA-Z0-9_]")


def safe_ident(text: str) -> str:
    base = _SMT_SAFE.sub("_", text)
    if base and base[0].isdigit():
        return f"n_{base}"
    return base


def sym(node_name: str, suffix: str) -> str:
    return f"{suffix}_{safe_ident(node_name)}"


def track(*parts: str) -> str:
    raw = "_".join(parts)
    ident = safe_ident(raw)
    if ident and ident[0].isdigit():
        return f"t_{ident}"
    return ident


def ite_chain(pairs: List[Tuple[str, str]], default: str) -> str:
    if not pairs:
        return default
    expr = default
    for cond, val in reversed(pairs):
        expr = f"(ite {cond} {val} {expr})"
    return expr


def freq_tolerance_bounds(period_tolerance: float) -> tuple[int, int, int]:
    den = 100
    tol_num = round(period_tolerance * den)
    return den - tol_num, den + tol_num, den


class Smt2Builder:
    def __init__(self) -> None:
        self._declarations: List[str] = []
        self._constraints: List[tuple[str, str | None, str | None]] = []

    def declare(self, text: str) -> None:
        self._declarations.append(text)

    def constraint(
        self,
        expr: str,
        *,
        track_id: str | None = None,
        hint: str | None = None,
    ) -> None:
        self._constraints.append((expr, track_id, hint))

    def _render(self, *, named_tracks: bool) -> str:
        lines: List[str] = []
        if named_tracks:
            lines.append("(set-option :produce-unsat-cores true)")
        lines.append("(set-logic QF_NIA)")
        lines.extend(self._declarations)
        for expr, track_id, _hint in self._constraints:
            if named_tracks and track_id is not None:
                lines.append(f"(assert (! {expr} :named {track_id}))")
            else:
                lines.append(f"(assert {expr})")
        lines.append("(check-sat)")
        lines.append("(get-model)")
        return "\n".join(lines) + "\n"

    def finish(
        self,
    ) -> tuple[str, str, Dict[str, str], List[tuple[str, str, str]]]:
        hints = {
            tid: hint
            for _expr, tid, hint in self._constraints
            if tid is not None and hint is not None
        }
        tracked = [
            (tid, expr, hint)
            for expr, tid, hint in self._constraints
            if tid is not None and hint is not None
        ]
        return (
            self._render(named_tracks=False),
            self._render(named_tracks=True),
            hints,
            tracked,
        )


def div_freq_relation_expr(
    *,
    freq_in: str,
    freq_out: str,
    ratio: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    return (
        f"(and "
        f"(> {freq_hw} 0) "
        f"(>= {rem} 0) "
        f"(< {rem} {ratio}) "
        f"(= {freq_in} (+ (* {freq_hw} {ratio}) {rem})) "
        f"(<= (* {freq_out} {tol_lo}) (* {freq_hw} {tol_den})) "
        f"(>= (* {freq_out} {tol_hi}) (* {freq_hw} {tol_den}))"
        f")"
    )


def div_freq_constraint_expr(
    *,
    active: str,
    freq_in: str,
    freq_out: str,
    ratio: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    relation = div_freq_relation_expr(
        freq_in=freq_in,
        freq_out=freq_out,
        ratio=ratio,
        freq_hw=freq_hw,
        rem=rem,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    return f"(=> {active} {relation})"


def pll_product_freq_relation_expr(
    *,
    freq_ref: str,
    freq_out: str,
    fbdiv: str,
    product: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    """ref * fbdiv = f_hw * product + rem，输出频率在容差内接近 f_hw。"""
    return (
        f"(and "
        f"(> {freq_hw} 0) "
        f"(>= {rem} 0) "
        f"(< {rem} {product}) "
        f"(= (* {freq_ref} {fbdiv}) (+ (* {freq_hw} {product}) {rem})) "
        f"(<= (* {freq_out} {tol_lo}) (* {freq_hw} {tol_den})) "
        f"(>= (* {freq_out} {tol_hi}) (* {freq_hw} {tol_den}))"
        f")"
    )


def pll_product_freq_constraint_expr(
    *,
    active: str,
    freq_ref: str,
    freq_out: str,
    fbdiv: str,
    product: str,
    freq_hw: str,
    rem: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    relation = pll_product_freq_relation_expr(
        freq_ref=freq_ref,
        freq_out=freq_out,
        fbdiv=fbdiv,
        product=product,
        freq_hw=freq_hw,
        rem=rem,
        tol_lo=tol_lo,
        tol_hi=tol_hi,
        tol_den=tol_den,
    )
    return f"(=> {active} {relation})"


def freq_within_tolerance_expr(
    freq_out: str,
    freq_want: str,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> str:
    return (
        f"(and "
        f"(<= (* {freq_want} {tol_lo}) (* {freq_out} {tol_den})) "
        f"(>= (* {freq_want} {tol_hi}) (* {freq_out} {tol_den}))"
        f")"
    )

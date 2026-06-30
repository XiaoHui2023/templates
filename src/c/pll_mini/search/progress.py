from __future__ import annotations

import time
from typing import Dict, List, Mapping, Sequence

from model.nodes import MuxNode, Tree


def mux_assignment_total(tree: Tree, free_muxes: Sequence[str]) -> int:
    if not free_muxes:
        return 0
    total = 1
    for name in free_muxes:
        node = tree.nodes[name]
        if not isinstance(node, MuxNode):
            continue
        total *= max(1, len(node.source))
    return total


def format_mux_assignment(
    assignment: Mapping[str, int],
    *,
    max_items: int = 4,
) -> str:
    if not assignment:
        return ""
    items = sorted(assignment.items())
    if len(items) <= max_items:
        return " ".join(f"{name}={sel}" for name, sel in items)
    head = items[:2]
    tail = items[-2:]
    mid = " … "
    return (
        " ".join(f"{name}={sel}" for name, sel in head)
        + mid
        + " ".join(f"{name}={sel}" for name, sel in tail)
    )


class ComponentSearchReporter:
    """子树求解内步进度；终端 Live 关闭时为 no-op。"""

    _REFRESH_INTERVAL_S = 0.1
    _REFRESH_EVERY_N = 256

    def __init__(
        self,
        tree: Tree,
        free_muxes: List[str],
        *,
        pll_ref: bool = False,
    ) -> None:
        from report.ui import active_progress_session

        self._session = active_progress_session()
        self._pll_ref = pll_ref
        self._mux_total = mux_assignment_total(tree, free_muxes)
        self._mux_current = 0
        self._inner_current = 0
        self._inner_total = 0
        self._phase = ""
        self._last_refresh = 0.0
        self._last_assignment: Dict[str, int] = {}
        self._trial_mux: Dict[str, int] = {}
        if self._session is not None:
            self._session.begin_component_search(
                kind="pll_ref" if pll_ref else "clk",
                mux_total=self._mux_total,
                free_muxes=free_muxes,
            )

    def mux_trial(self, assignment: Mapping[str, int]) -> None:
        self._mux_current += 1
        self._last_assignment = dict(assignment)
        self._inner_current = 0
        self._inner_total = 0
        self._emit(
            "mux枚举",
            current=self._mux_current,
            total=self._mux_total,
            detail=format_mux_assignment(assignment),
        )

    def begin_ref_mux(self, tree: Tree, ref_mux_free: List[str]) -> None:
        self._inner_total = mux_assignment_total(tree, ref_mux_free)
        self._inner_current = 0
        self._emit(
            "inno参考mux",
            current=0,
            total=self._inner_total,
            detail=format_mux_assignment(self._trial_mux),
            force=True,
        )

    def begin_div_assignment(self, divs: Sequence[str]) -> None:
        active_divs = list(divs)
        self._inner_current = 0
        self._inner_total = len(active_divs)
        detail = ", ".join(active_divs[:6])
        if len(active_divs) > 6:
            detail = f"{detail},..."
        self._emit(
            "分频求解",
            current=0,
            total=max(1, self._inner_total),
            detail=detail,
            force=True,
        )

    def div_trial(
        self,
        div_name: str,
        index: int,
        total: int,
        *,
        f_in: int | None = None,
        want_out: int | None = None,
        ratio: int | None = None,
        failed: str = "",
    ) -> None:
        self._inner_current = index
        parts = [div_name]
        if f_in is not None:
            parts.append(f"in={f_in}")
        if want_out is not None:
            parts.append(f"out={want_out}")
        if ratio is not None:
            parts.append(f"ratio={ratio}")
        if failed:
            parts.append(f"fail={failed}")
        self._emit(
            "分频求解",
            current=index,
            total=max(1, total),
            detail=" ".join(parts),
            force=bool(failed),
        )

    def begin_ref_div(self, ref_divs: Sequence[str]) -> None:
        if not ref_divs:
            self.phase("频率传播")
            return
        self._inner_current = 0
        self._inner_total = 0
        self._emit(
            "inno参考div",
            detail=", ".join(ref_divs),
            force=True,
        )

    def ref_div_candidates(
        self,
        div_name: str,
        candidates: Sequence[int],
    ) -> None:
        if not candidates:
            self._emit(
                "inno参考div",
                detail=f"{div_name}: 无候选",
                force=True,
            )
            return
        if self._inner_total <= 0:
            self._inner_total = len(candidates)
        else:
            self._inner_total *= max(1, len(candidates))
        preview = ",".join(str(v) for v in candidates[:8])
        if len(candidates) > 8:
            preview = f"{preview},..."
        self._emit(
            "inno参考div候选",
            current=0,
            total=len(candidates),
            detail=f"{div_name}: {preview}",
            force=True,
        )

    def ref_div_trial(
        self,
        div_name: str,
        ratio: int,
        index: int,
        total: int,
    ) -> None:
        self._inner_current += 1
        self._emit(
            "inno参考div枚举",
            current=index,
            total=total,
            detail=f"{div_name}={ratio}",
        )

    def pll_trial(
        self,
        pll_name: str,
        pll_kind: str,
        ref_hz: int,
        out_hz: int,
    ) -> None:
        self._emit(
            "PLL系数",
            detail=f"{pll_name}({pll_kind}) ref={ref_hz} out={out_hz}",
            force=True,
        )

    def ref_mux_trial(self, ref_assignment: Mapping[str, int]) -> None:
        self._inner_current += 1
        combined = {**self._trial_mux, **ref_assignment}
        self._emit(
            "inno参考mux",
            current=self._inner_current,
            total=self._inner_total,
            detail=format_mux_assignment(combined),
        )

    def set_trial_mux(self, trial_mux: Mapping[str, int]) -> None:
        self._trial_mux = dict(trial_mux)

    def phase(self, name: str, *, detail: str = "") -> None:
        self._emit(name, detail=detail, force=True)

    def end(self) -> None:
        if self._session is not None:
            self._session.end_component_search()

    def exhaustion_summary(
        self,
        *,
        free_muxes: Sequence[str],
        free_divs: Sequence[str],
    ) -> str:
        parts: List[str] = []
        if self._mux_total > 0:
            parts.append(f"mux 枚举 {self._mux_current}/{self._mux_total}")
        elif free_muxes:
            parts.append(f"自由 mux: {', '.join(free_muxes)}")
        if free_divs:
            parts.append(f"自由 div: {', '.join(free_divs)}")
        if self._inner_total > 0:
            parts.append(
                f"内层候选约 {max(self._inner_current, 0)}/{self._inner_total}"
            )
        if self._pll_ref:
            parts.append("PLL 参考路径")
        if not parts:
            return "已穷尽候选 mux、分频与 PLL 组合"
        return "；".join(parts)

    def _emit(
        self,
        phase: str,
        *,
        current: int | None = None,
        total: int | None = None,
        detail: str = "",
        force: bool = False,
    ) -> None:
        if self._session is None:
            return
        now = time.perf_counter()
        phase_changed = phase != self._phase
        self._phase = phase
        if current is not None:
            tick = current
        elif phase in (
            "mux枚举",
            "inno参考mux",
            "inno参考div枚举",
            "分频求解",
        ):
            tick = self._mux_current if phase == "mux枚举" else self._inner_current
        else:
            tick = None
        if (
            not force
            and not phase_changed
            and tick is not None
            and tick % self._REFRESH_EVERY_N != 0
            and now - self._last_refresh < self._REFRESH_INTERVAL_S
        ):
            return
        self._last_refresh = now
        self._session.tick_component_search(
            phase,
            current=current,
            total=total,
            detail=detail,
            force=force or phase_changed,
        )

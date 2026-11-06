from __future__ import annotations

from dataclasses import dataclass

from model.arithmetic import freq_within_tolerance
from reg_paths import reg_key_to_c_ident
from registers.program import (
    WriteTemplate,
    WritePartTemplate,
    keys_slot_specs,
    group_reg_write_templates,
    slot_param_name,
)

from node.discovery import InputForm
from node.validation import normalized_choice
from pydantic import field_validator

from typing import Literal
from load.regmodel import RegModelIndex

from pydantic import Field

from node.synthesis import SynthesizedNode


class PllInnoNode(SynthesizedNode):
    def verification_target(self, model, port):
        return model.port_hz(port)

    plan_group = "pll"
    program_variant = "inno"
    function_prefix = "pll_mini_config_pll_"
    configuration_key = "pll_cfg"
    ready_key = "lock"
    poll_function = "pll_mini_wait_lock"
    poll_parameter = "lock_mask"
    frequency_rule = "pll_freq"
    constraint_fields = {"pll_freq": ("freq",), "fixed_freq": ("freq",)}
    output_names = ("0", "1")
    reg_keys = frozenset(
        (
            "fbdiv",
            "lock",
            "pd",
            "postdiv1[0]",
            "postdiv1[1]",
            "postdiv2[0]",
            "postdiv2[1]",
            "refdiv",
        )
    )
    formula = (
        "f_out[group] = f_ref * fbdiv // (refdiv * postdiv1[group] * postdiv2[group])"
    )
    input_forms = (InputForm("pll", "pll_kind", ("inno",)),)
    """Concrete pll_inno node plugin."""

    kind: Literal["pll_inno"] = "pll_inno"
    pll_kind: Literal["inno"] = Field(default="inno", description="Device variant")

    def search(self, ref, targets, settings, tolerance):
        lo, hi, den = tolerance
        return search_pll_inno(ref, targets, tol_lo=lo, tol_hi=hi, tol_den=den)

    def diagnose(self, ref, targets, settings, tolerance):
        lo, hi, den = tolerance
        return _diagnose_pll_inno(
            ref, targets, tol_lo=lo, tol_hi=hi, tol_den=den
        ).format()

    def configuration(self, vars_map):
        cfg: dict[str, int] = {
            "pd": 0,
            "refdiv": vars_map["refdiv"],
            "fbdiv": vars_map["fbdiv"],
        }
        groups = self.output_groups
        for group_id in groups:
            p1_key, p2_key = inno_postdiv_reg_keys(group_id)
            cfg[p1_key] = inno_postdiv_to_reg(vars_map[f"postdiv1_{group_id}"])
            cfg[p2_key] = inno_postdiv_to_reg(vars_map[f"postdiv2_{group_id}"])
        return cfg

    def actual_frequency(self, ref, values, group):
        return pll_inno_actual_hz(
            ref,
            values.get("fbdiv", 0),
            values.get("refdiv", 0),
            values.get(f"postdiv1_{group}", 0),
            values.get(f"postdiv2_{group}", 0),
        )

    def slot_specs(self, index):
        specs: list[tuple[str, tuple[str, ...]]] = [
            ("inno_pd", ("pd",)),
            *keys_slot_specs(("refdiv", "fbdiv"), "inno_div", self, index),
        ]
        for group_id in self.output_groups:
            p1_key, p2_key = inno_postdiv_reg_keys(group_id)
            specs.extend(
                keys_slot_specs(
                    (p1_key, p2_key), f"inno_postdiv_{group_id}", self, index
                )
            )
        return tuple(specs)

    def configuration_keys(self, cfg_by_freq):
        keys = set().union(*(cfg.keys() for cfg in cfg_by_freq.values()))
        return tuple(
            key
            for key in (
                "refdiv",
                "fbdiv",
                *(
                    key
                    for group in self.output_groups
                    for key in inno_postdiv_reg_keys(group)
                ),
            )
            if key in keys
        )

    def write_templates(self, index):
        return _inno_write_templates(self.output_groups, index, self)

    @field_validator("pll_kind", mode="before")
    @classmethod
    def _normalize_variant(cls, value):
        return normalized_choice(value, ("inno",), "pll_kind")


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
                "单输出也无合法候选的端口：" + ", ".join(self.missing_single_groups)
            )
        if self.best_shared:
            first = self.best_shared[0]
            lines.append(
                f"最接近的共用候选：refdiv={first.refdiv}, fbdiv={first.fbdiv}"
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


def _fmt_hz(hz: int) -> str:
    if hz % 1_000_000 == 0:
        return f"{hz // 1_000_000} MHz ({hz} Hz)"
    if hz % 1_000 == 0:
        return f"{hz // 1_000} kHz ({hz} Hz)"
    return f"{hz} Hz"


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
    active_groups = {group: hz for group, hz in group_out_hz.items() if hz > 0}
    if not active_groups:
        return None

    per_group = {
        group_id: _inno_group_candidates(
            ref_hz,
            group_id,
            target_hz,
            tol_lo=tol_lo,
            tol_hi=tol_hi,
            tol_den=tol_den,
        )
        for group_id, target_hz in active_groups.items()
    }
    shared_keys: set[tuple[int, int]] | None = None
    for candidates in per_group.values():
        keys = set(candidates)
        shared_keys = keys if shared_keys is None else shared_keys & keys
    if not shared_keys:
        return None

    best: tuple[int, int, dict[str, int]] | None = None
    for refdiv, fbdiv in sorted(shared_keys):
        vars_map: dict[str, int] = {"refdiv": refdiv, "fbdiv": fbdiv}
        total_error = 0
        worst_error = 0
        for group_id, candidates in per_group.items():
            item = candidates[(refdiv, fbdiv)]
            vars_map[f"postdiv1_{group_id}"] = item.postdiv1
            vars_map[f"postdiv2_{group_id}"] = item.postdiv2
            total_error += item.abs_error_hz
            worst_error = max(worst_error, item.abs_error_hz)
        for group_id in group_out_hz:
            p1_key = f"postdiv1_{group_id}"
            p2_key = f"postdiv2_{group_id}"
            if p1_key not in vars_map:
                vars_map[p1_key] = 1
                vars_map[p2_key] = 1
        if best is None or (total_error, worst_error) < (best[0], best[1]):
            best = (total_error, worst_error, vars_map)
    return best[2] if best is not None else None


def _diagnose_pll_inno(
    ref_hz: int,
    group_out_hz: dict[str, int],
    *,
    tol_lo: int,
    tol_hi: int,
    tol_den: int,
) -> PllSearchDiagnosis:
    active_groups = {group: hz for group, hz in group_out_hz.items() if hz > 0}
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
                actual = pll_inno_actual_hz(ref_hz, fbdiv, refdiv, postdiv1, postdiv2)
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


def inno_fbdiv_legal(fbdiv: int) -> bool:
    if 0 <= fbdiv <= 7:
        return False
    if fbdiv == 11:
        return False
    return True


def pll_inno_actual_hz(
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


def inno_postdiv_to_reg(postdiv: int) -> int:
    if postdiv < 1 or postdiv > 7:
        raise ValueError(f"inno postdiv {postdiv} 应在 1～7")
    return postdiv - 1


POSTDIV_PAIRS = tuple((p1, p2) for p1 in range(1, 8) for p2 in range(1, 8))


def inno_postdiv_reg_keys(group_id: str) -> tuple[str, str]:
    return f"postdiv1[{group_id}]", f"postdiv2[{group_id}]"


def _inno_write_templates(
    output_groups: list[str],
    index: RegModelIndex,
    template_node: SynthesizedNode,
) -> tuple[WriteTemplate, ...]:

    templates: list[WriteTemplate] = []
    pd_ref = index.resolve(
        template_node.regs["pd"],
        ctx=f"pll node {template_node.name!r} regs.pd",
    )
    templates.append(
        WriteTemplate(
            slot_param_name("inno_pd"),
            (
                WritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "1",
                    "pd assert",
                ),
            ),
            pd_ref.reg.path,
            "inno_pd",
        )
    )
    templates.extend(
        group_reg_write_templates(
            index,
            template_node,
            ("refdiv", "fbdiv"),
            slot_id="inno_div",
            value_expr_for_key=reg_key_to_c_ident,
            comment_for_key=lambda key: key,
        )
    )
    templates.append(
        WriteTemplate(
            slot_param_name("inno_pd"),
            (
                WritePartTemplate(
                    pd_ref.effective_lsb,
                    pd_ref.effective_width,
                    "0",
                    "pd release",
                ),
            ),
            pd_ref.reg.path,
            "inno_pd",
        )
    )
    if not output_groups:
        raise ValueError("pll_kind inno 须有两路输出，output_groups 为空")
    for group_id in output_groups:
        p1_key, p2_key = inno_postdiv_reg_keys(group_id)
        templates.extend(
            group_reg_write_templates(
                index,
                template_node,
                (p1_key, p2_key),
                slot_id=f"inno_postdiv_{group_id}",
                value_expr_for_key=reg_key_to_c_ident,
                comment_for_key=lambda key, p1=p1_key, gid=group_id: (
                    f"out[{gid}] {key}" if key == p1 else key
                ),
            )
        )
    return tuple(templates)

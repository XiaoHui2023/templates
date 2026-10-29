from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from node.base import _coerce_optional_int, _coerce_optional_source_field
from node.behaviors import TransparentNode


class ClkNode(TransparentNode):
    is_target = True

    def fixed_hz(self, group: str = "") -> int | None:
        """负频率仅表示不约束。"""
        return self.freq if self.freq is not None and self.freq > 0 else None

    def verify(self, tree, model, tolerance: float) -> list:
        """回放目标端口频率。"""
        return verify_node(self, tree, model, tolerance)

    kind: Literal["clk"] = "clk"
    freq: Optional[int] = Field(
        default=None,
        description="典型频率，单位 Hz；省略表示不参与频率约束；"
        "正数表示目标频率并参与约束求解；负数仅不约束 resolved_freq。",
    )
    source: str = Field("", description="前级引用；省略表示无前级。")

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_optional_freq(cls, value: Any) -> Any:
        return _coerce_optional_int(value)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: Any) -> str:
        return _coerce_optional_source_field(value)

    @model_validator(mode="after")
    def _validate_clk_freq(self) -> ClkNode:
        if self.freq is not None and self.freq == 0:
            raise ValueError(
                f"clk 节点 {self.name!r} freq 为 0 非法；"
                f"正频率应大于等于 1，不约束请省略或填负数"
            )
        return self


def verify_node(node, tree, model, period_tolerance):
    from model.arithmetic import freq_tolerance_bounds
    from model.freq_graph import (
        Port,
        collect_freq_targets,
        collect_non_frequency_targets,
        node_has_upstream_ref,
        parent_port_for_child,
        walk_path_upstream,
    )
    from model.verify import VerifyIssue, _hz_mhz

    issues = []
    collect_freq_targets(tree)
    non_constraint_clks = frozenset(collect_non_frequency_targets(tree))
    tol_lo, tol_hi, tol_den = freq_tolerance_bounds(period_tolerance)
    for name, node in [(node.name, node)]:
        if name in non_constraint_clks:
            continue
        if not node_has_upstream_ref(node):
            continue
        parent_port = parent_port_for_child(tree, name)
        f_self = model.port_hz(Port(name, ""))
        f_parent = model.port_hz(parent_port)
        if f_self <= 0 or f_parent <= 0:
            continue
        if f_self != f_parent:
            issues.append(
                VerifyIssue(
                    headline=f"clk {name} 与前级频率不一致",
                    formula="f_clk = f_ref",
                    detail=(
                        f"前级 {_hz_mhz(model.port_hz(parent_port))}，"
                        f"clk {_hz_mhz(model.port_hz(Port(name, '')))}"
                    ),
                    path_nodes=walk_path_upstream(tree, name, model=model),
                )
            )

    return issues

from __future__ import annotations

from typing import ClassVar

from pydantic import (
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from reg_paths import validate_regs_exact

from .base import NodeBase, _coerce_optional_source_field, _validation_node_name


class SynthesizedNode(NodeBase):
    """Fixed output targets with plugin-owned fitting and staged programming."""

    is_anchor = True
    independent_outputs = True
    output_names: ClassVar[tuple[str, ...]] = ()
    reg_keys: ClassVar[frozenset[str]]
    configuration_key: ClassVar[str]
    program_variant: ClassVar[str]
    function_prefix: ClassVar[str]
    frequency_rule: ClassVar[str]
    ready_key: ClassVar[str]
    poll_function: ClassVar[str]
    poll_parameter: ClassVar[str]
    formula: ClassVar[str]
    source: str = Field("")
    freq: int | dict[str, int] | None = None
    regs: dict[str, str] = Field(default_factory=dict)

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value):
        return _coerce_optional_source_field(value)

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_targets(cls, value):
        if value is None or value == "":
            return None
        return (
            {str(k): int(v) for k, v in value.items()}
            if isinstance(value, dict)
            else int(value)
        )

    @model_validator(mode="after")
    def _validate_targets_and_registers(self, info: ValidationInfo):
        name = _validation_node_name(self, info)
        if self.freq is None:
            raise ValueError(f"nodes[{name!r}].freq is required")
        if isinstance(self.freq, dict):
            if not self.output_names or set(self.freq) != set(self.output_names):
                raise ValueError(
                    f"nodes[{name!r}].freq keys must be {self.output_names!r}"
                )
            if any(value < 1 for value in self.freq.values()):
                raise ValueError(f"nodes[{name!r}].freq values must be positive")
        elif self.freq < 1:
            raise ValueError(f"nodes[{name!r}].freq must be positive")
        validate_regs_exact(self.regs, self.reg_keys, node_name=name, kind=self.kind)
        return self

    @computed_field
    @property
    def output_groups(self) -> list[str]:
        return list(self.output_names)

    def freq_for_group(self, group):
        return self.freq.get(group) if isinstance(self.freq, dict) else self.freq

    def fixed_hz(self, group=""):
        return self.freq_for_group(group)

    def add_constraints(self, builder):
        from model.freq_graph import output_ports, parent_port_for_child
        from model.smt import act, freq, port_suffix

        name = self.name
        ports = output_ports(builder.tree, name)
        if any(self.fixed_hz(port.group) is not None for port in ports):
            builder._add(f"{name}__fixed_freq_active", act(name))
        if self.regs:
            try:
                parent = parent_port_for_child(builder.tree, name)
            except ValueError:
                parent = None
            if parent is not None:
                builder._add(
                    f"{name}__parent_active", f"(=> {act(name)} {act(parent.node)})"
                )
        for port in ports:
            fixed = self.fixed_hz(port.group)
            if fixed is not None:
                builder._add(
                    f"{name}__{self.frequency_rule}__{port_suffix(port)}",
                    f"(=> {act(name)} (= {freq(port)} {fixed}))",
                )

    def fit(self, tree, model, settings):
        from model.arithmetic import freq_tolerance_bounds
        from model.freq_graph import Port, parent_port_for_child, static_port_hz

        values = model.values(self.name)
        if not self.regs or "coefficients" in values:
            return
        parent = parent_port_for_child(tree, self.name)
        ref = model.port_hz(parent) or static_port_hz(tree, model, parent)
        if ref <= 0:
            raise RuntimeError(f"nodes[{self.name!r}] invalid reference frequency")
        targets = {
            group: model.port_hz(Port(self.name, group)) or self.fixed_hz(group) or 0
            for group in self.output_groups or [""]
        }
        tolerance = freq_tolerance_bounds(settings.period_tolerance)
        coefficients = self.search(ref, targets, settings, tolerance)
        if coefficients is None:
            raise RuntimeError(
                f"nodes[{self.name!r}] {self.kind}: "
                + self.diagnose(ref, targets, settings, tolerance)
            )
        values["coefficients"] = coefficients

    def search(self, ref, targets, settings, tolerance):
        raise NotImplementedError

    def diagnose(self, ref, targets, settings, tolerance):
        return (
            f"no legal coefficients within tolerance; ref_hz={ref}, targets={targets}"
        )

    def configuration(self, coefficients):
        raise NotImplementedError

    def actual_frequency(self, ref, coefficients, group):
        raise NotImplementedError

    def slot_specs(self, index):
        raise NotImplementedError

    def configuration_keys(self, configurations):
        raise NotImplementedError

    def write_templates(self, index):
        raise NotImplementedError

    def resolved_values(self, model):
        coefficients = model.values(self.name).get("coefficients", {})
        return (
            {self.configuration_key: self.configuration(coefficients)}
            if self.regs and coefficients
            else {}
        )

    def verification_target(self, model, port):
        return model.port_hz(port) or self.fixed_hz(port.group) or 0

    def frequency_matches(self, target, actual, tolerance):
        from model.arithmetic import freq_within_tolerance

        lo, hi, den = tolerance
        return freq_within_tolerance(target, actual, tol_lo=lo, tol_hi=hi, tol_den=den)

    def verify(self, tree, model, tolerance):
        from model.arithmetic import freq_tolerance_bounds
        from model.freq_graph import output_ports, parent_port_for_child, static_port_hz
        from model.verify import VerifyIssue, _hz_mhz, _path_for_node

        coefficients = model.values(self.name).get("coefficients", {})
        if not coefficients:
            return []
        parent = parent_port_for_child(tree, self.name)
        ref = model.port_hz(parent) or static_port_hz(tree, model, parent)
        bounds = freq_tolerance_bounds(tolerance)
        issues = []
        for port in output_ports(tree, self.name):
            target = self.verification_target(model, port)
            actual = self.actual_frequency(ref, coefficients, port.group)
            if target > 0 and not self.frequency_matches(target, actual, bounds):
                issues.append(
                    VerifyIssue(
                        headline=f"{self.kind} {self.name} 系数与频率不一致",
                        formula=self.formula,
                        detail=f"ref={_hz_mhz(ref)}, target={_hz_mhz(target)}, actual={_hz_mhz(actual)}, coefficients={coefficients}",
                        path_nodes=_path_for_node(tree, self.name, model),
                    )
                )
        return issues

    def ready_view(self, index):
        ref = index.resolve(
            self.regs[self.ready_key], ctx=f"nodes[{self.name!r}].regs.{self.ready_key}"
        )
        return ref.reg.addr_macro, f"0x{ref.effective_mask & 0xFFFFFFFF:X}"

    def build_plan_group(self, nodes, index, resolved):
        from registers.program import build_program

        return build_program(
            [node for node in nodes if node.plan_group == self.plan_group],
            index,
            resolved,
        )

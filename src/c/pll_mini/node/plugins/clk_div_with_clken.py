from __future__ import annotations

from typing import Literal

from model.freq_graph import Port, parent_port_for_child
from model.smt import act, freq
from pydantic import Field, computed_field, model_validator

from node.base import NodeBase


class ClkDivWithClkenNode(NodeBase):
    """核心时钟直通，两个总线输出共用一个分频控制。"""

    plan_priority = 10
    kind: Literal["clk_div_with_clken"] = "clk_div_with_clken"
    source: str = Field(default="", description="上游时钟引用")
    ratio: Literal[2, 3, 4, 6] | None = Field(default=None, description="共用分频比")
    outputs: list[str] = Field(default_factory=list, description="可省略的固定输出组")
    reg: str = Field(default="", description="分频编码字段路径")
    regs: dict[str, str] = Field(
        default_factory=dict, description="可选 div、rst、load 字段路径"
    )

    @computed_field
    @property
    def output_groups(self) -> list[str]:
        """返回固定的三个硬件输出。"""
        return ["clk_arm_core", "hclk", "hclken"]

    @model_validator(mode="after")
    def _validate_controls(self):
        if self.outputs and self.outputs != self.output_groups:
            raise ValueError(f"outputs 应为 {self.output_groups}")
        if set(self.regs) - {"div", "rst", "load"}:
            raise ValueError("regs 仅支持 div、rst、load")
        if self.reg and self.regs.get("div") and self.reg != self.regs["div"]:
            raise ValueError("reg 与 regs.div 不可指向不同字段")
        return self

    def add_constraints(self, builder) -> None:
        """三个输出共享分频比，核心输出保持直通。"""
        name = self.name
        ratio = builder.variable(name, "ratio")
        builder._declare(ratio, "Int")
        domain = " ".join(f"(= {ratio} {value})" for value in (2, 3, 4, 6))
        builder._add(
            f"{name}__ratio_domain", f"(or {domain})", paths=(f"nodes[{name!r}].ratio",)
        )
        if self.ratio is not None:
            builder._add(f"{name}__ratio_fixed", f"(= {ratio} {self.ratio})")
        if not self.source:
            builder._add(f"{name}__no_source_inactive", f"(not {act(name)})")
            return
        parent = parent_port_for_child(builder.tree, name)
        core, bus, enable = [freq(Port(name, output)) for output in self.output_groups]
        hw = f"(div {freq(parent)} {ratio})"
        builder._add(f"{name}__parent_active", f"(=> {act(name)} {act(parent.node)})")
        builder._add(
            f"{name}__core_passthrough", f"(=> {act(name)} (= {core} {freq(parent)}))"
        )
        builder._add(f"{name}__shared_bus", f"(=> {act(name)} (= {bus} {enable}))")
        builder._add(
            f"{name}__bus_division",
            f"(=> {act(name)} (and (<= (* {bus} {builder.tol_lo}) (* {hw} {builder.tol_den})) (>= (* {bus} {builder.tol_hi}) (* {hw} {builder.tol_den}))))",
        )

    def read_solution(self, builder, raw, model) -> None:
        """读取三个输出共用的分频比。"""
        model.values(self.name)["ratio"] = int(
            raw.get(builder.variable(self.name, "ratio"), self.ratio or 2)
        )

    def control_encodings(self, builder) -> dict[str, tuple[str, str]]:
        """提供与 clock_tree 相同的 0、2、4、8 规范编码。"""
        path = self.reg or self.regs.get("div")
        ratio = builder.variable(self.name, "ratio")
        encoded = f"(ite (= {ratio} 2) 0 (ite (= {ratio} 3) 2 (ite (= {ratio} 4) 4 8)))"
        return {"reg" if self.reg else "div": (path, encoded)} if path else {}

    def resolved_values(self, model) -> dict[str, object]:
        """返回共用分频比。"""
        return {"ratio": self.ratio or model.values(self.name).get("ratio", 2)}

    def static_hz(self, tree, model, group: str, upstream) -> int:
        """回放核心和总线输出频率。"""
        value = upstream(self.source) if self.source else 0
        ratio = self.ratio or model.values(self.name).get("ratio", 2)
        return value if group == "clk_arm_core" else value // ratio

    def verify(self, tree, model, tolerance: float) -> list:
        """独立检查三个输出关系及共用分频比。"""
        from model.arithmetic import freq_tolerance_bounds, freq_within_tolerance
        from model.verify import VerifyIssue

        if not self.source:
            return []
        parent = parent_port_for_child(tree, self.name)
        input_hz = model.port_hz(parent)
        actual = [model.port_hz(Port(self.name, group)) for group in self.output_groups]
        if input_hz <= 0 or not any(actual):
            return []
        ratio = model.values(self.name).get("ratio", 0)
        lo, hi, den = freq_tolerance_bounds(tolerance)
        if (
            ratio not in (2, 3, 4, 6)
            or actual[0] != input_hz
            or actual[1] != actual[2]
            or not freq_within_tolerance(
                actual[1], input_hz // ratio, tol_lo=lo, tol_hi=hi, tol_den=den
            )
        ):
            return [
                VerifyIssue(
                    f"nodes[{self.name!r}] 三输出频率关系错误",
                    "core=in; hclk=hclken=in/ratio",
                    f"in={input_hz}, outputs={actual}, ratio={ratio}",
                    (self.name,),
                )
            ]
        return []

    def plan_patches(self, index, settings, resolved) -> list:
        """物理分频器只生成一组字段写入。"""
        from registers.plan import _patch

        values = {
            "div": {2: 0, 3: 2, 4: 4, 6: 8}[resolved.ratio],
            "rst": 0 if settings.div_reg_high_means_reset else 1,
            "load": 1,
        }
        paths = dict(self.regs)
        if self.reg:
            paths["div"] = self.reg
        return [
            _patch(
                index,
                node_name=self.name,
                raw_path=path,
                value=values[key],
                note=f"{self.name} {key}={values[key]}",
            )
            for key, path in paths.items()
        ]

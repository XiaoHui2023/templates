from __future__ import annotations

import re
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sv.agent.clock_tree.reg_paths import (
    DIV_REG_KEYS,
    DTO_REG_KEYS,
    PLL_REG_KEYS,
    RegsMap,
    flatten_regs,
    validate_reg_path,
    validate_regs_against_allowed,
)

PllKind = Literal["PLL_TCI", "PLL_SC", "PLL_DW"]
_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class Source(BaseModel):
    name: str = Field(..., description="驱动源节点名，须与本 tree 的 nodes 中某一 name 相同。")
    key: int = Field(
        0,
        description="sources 关联数组键；mux 用 0、1 等整数键；非 mux 一般为 0。",
    )


class NodeCommon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="节点唯一名，兼作展开后 tree 类成员名。")
    path: str = Field(..., min_length=1, description="该节点在设计中的实例层次路径。")
    frequence: int = Field(
        ...,
        ge=1,
        description="典型频率，单位 Hz；展开后在 node_base 上作 rand，由约束软指向该值。",
    )
    sources: List[Source] = Field(
        default_factory=list,
        description="驱动本节点的来源列表。",
    )
    allow_bad_duty: bool = Field(
        False,
        description="允许实测占空比超出全局限定区间；默认否，一般不必设置。",
    )


class ClkNode(NodeCommon):
    kind: Literal["clk"] = "clk"


class DivNode(NodeCommon):
    kind: Literal["div"] = "div"
    div_ratio: int = Field(
        1,
        ge=1,
        description="分频比；随机化约束为前级频率整除该值。",
    )
    regs: RegsMap = Field(
        default_factory=dict,
        description="分频相关 field：键为逻辑名 ratio、enable、bypass；"
        "值为自 RAL 根起的点分路径，或一层 block 名下挂 field 短名。",
    )

    @model_validator(mode="after")
    def _validate_div_regs(self) -> DivNode:
        if self.regs:
            validate_regs_against_allowed(
                self.regs, DIV_REG_KEYS, node_name=self.name, kind="div"
            )
        return self


class DtoNode(NodeCommon):
    kind: Literal["dto"] = "dto"
    div_ratio: int = Field(
        1,
        ge=1,
        description="分频比；随机化约束为前级频率整除该值。",
    )
    regs: RegsMap = Field(
        default_factory=dict,
        description="占空比变换相关 field：键为 ratio、duty、enable、bypass；"
        "值为点分全路径或一层 block 下 field 短名。",
    )

    @model_validator(mode="after")
    def _validate_dto_regs(self) -> DtoNode:
        if self.regs:
            validate_regs_against_allowed(
                self.regs, DTO_REG_KEYS, node_name=self.name, kind="dto"
            )
        return self


class GateNode(NodeCommon):
    kind: Literal["gate"] = "gate"
    reg_gate: Optional[str] = Field(
        None,
        description="门控 field 自 RAL 根起的点分路径；省略或 null 表示不用寄存器。",
    )

    @model_validator(mode="after")
    def _validate_gate_reg(self) -> GateNode:
        if self.reg_gate:
            validate_reg_path(self.reg_gate, ctx=f"gate 节点 {self.name!r} reg_gate")
        return self


class MuxNode(NodeCommon):
    kind: Literal["mux"] = "mux"
    sel: int = Field(0, ge=0, description="mux 选择值。")

    @model_validator(mode="after")
    def _validate_mux_sources(self) -> MuxNode:
        if not self.sources:
            raise ValueError(f"mux 节点 {self.name!r} 须至少一条 source")
        keys = [s.key for s in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError(f"mux 节点 {self.name!r} 的 source.key 不得重复")
        return self


class InvNode(NodeCommon):
    kind: Literal["inv"] = "inv"


class PllNode(NodeCommon):
    kind: Literal["pll"] = "pll"
    pll_kind: PllKind = Field(..., description="pll 种类枚举名。")
    regs: RegsMap = Field(
        default_factory=dict,
        description="PLL field：键须属于该 pll_kind 允许集合；"
        "值为点分全路径或一层 block 下 field 短名。",
    )

    @model_validator(mode="after")
    def _validate_pll_regs(self) -> PllNode:
        if self.regs:
            validate_regs_against_allowed(
                self.regs,
                PLL_REG_KEYS[self.pll_kind],
                node_name=self.name,
                kind=f"pll({self.pll_kind})",
            )
        return self


class WireNode(NodeCommon):
    kind: Literal["wire"] = "wire"


Node = Annotated[
    Union[ClkNode, DivNode, DtoNode, GateNode, MuxNode, InvNode, PllNode, WireNode],
    Field(discriminator="kind"),
]


class Tree(BaseModel):
    name: str = Field(..., min_length=1, description="时钟树名，兼作展开后 SV 类型名片段与建树函数名片段。")
    nodes: List[Node] = Field(..., min_length=1, description="本棵时钟树的节点列表。")
    settings: dict[str, int] = Field(
        default_factory=dict,
        description="本树设置项取值，键须与根配置 setting_defs 中各项 name 一致。",
    )

    @model_validator(mode="after")
    def _validate_name(self) -> Tree:
        if not _SV_ID.match(self.name):
            raise ValueError(
                f"tree.name {self.name!r} 须为合法 SystemVerilog 标识符片段"
            )
        return self


def validate_nodes_graph(nodes: List[Node]) -> None:
    """校验节点名唯一性与 sources 连线规则。

    Raises:
        ValueError: 节点名重复、source 指向未知节点，或非 mux 的 source 条数违反规则时。
    """
    names = [n.name for n in nodes]
    if len(names) != len(set(names)):
        dup = {x for x in names if names.count(x) > 1}
        raise ValueError(f"nodes.name 须唯一，重复: {sorted(dup)}")

    known = set(names)
    for node in nodes:
        for src in node.sources:
            if src.name not in known:
                raise ValueError(
                    f"节点 {node.name!r} 的 source.name {src.name!r} "
                    f"不在 nodes 的 name 集合中"
                )
        if node.kind != "mux":
            if len(node.sources) > 1:
                raise ValueError(
                    f"非 mux 节点 {node.name!r} 至多允许一条 source"
                )

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, model_validator

NodeKind = Literal["clk", "div", "gate", "mux", "inv", "pll", "wire"]


class Source(BaseModel):
    name: str = Field(..., description="驱动源节点名，须与 nodes 中某一 name 相同。")
    key: str = Field(
        "",
        description="sources 关联数组键；非 mux 留空；mux 用 0、1 等字符串键。",
    )


class Node(BaseModel):
    name: str = Field(..., min_length=1, description="节点唯一名。")
    kind: NodeKind = Field(..., description="节点种类。")
    frequencies: List[int] = Field(
        default_factory=list,
        description="典型频率列表，单位 Hz；主要用于 kind 为 clk 的节点。",
    )
    path: str = Field(..., min_length=1, description="该节点在设计中的实例层次路径。")
    sources: List[Source] = Field(
        default_factory=list,
        description="驱动本节点的来源列表。",
    )
    allow_bad_duty: bool = Field(
        False,
        description="允许实测占空比超出全局限定区间；默认否，一般不必设置。",
    )


class Models(BaseModel):
    nodes: List[Node] = Field(..., min_length=1, description="时钟树节点列表。")
    vars: Dict[str, Any] = Field(
        default_factory=dict,
        description="用户自定义变量，模板内以 vars 引用，不做校验。",
    )
    class_prefix: str = Field(
        "clk_tree_",
        min_length=1,
        description="类型名前缀，与固定后缀拼接；建议含末尾下划线。如 tree、manifest、node_base、clk、node_if 等。",
    )
    min_freq_hz: int = Field(
        500,
        ge=500,
        description="可判定为仍活动的最低频率 Hz，非最高时钟；用于超时与最长可测周期 1/min_freq_hz 秒。",
    )
    stable_cycles: int = Field(
        3,
        ge=2,
        description="连续多少个周期落在容差内则置 stable。",
    )
    period_tolerance: float = Field(
        0.05,
        gt=0.0,
        lt=1.0,
        description="判定 stable 时相邻周期相对偏差上限。",
    )
    duty_min: float = Field(
        0.50,
        ge=0.0,
        le=1.0,
        description="允许占空比下限，份额 0～1，默认 0.50。",
    )
    duty_max: float = Field(
        0.66,
        ge=0.0,
        le=1.0,
        description="允许占空比上限，份额 0～1，默认 0.66。",
    )
    name_constraint_default: str = Field("cst_default", description="默认约束块名。")
    name_constraint_user: str = Field("cst_user", description="用户约束块名。")
    name_on_main: str = Field("main", description="主流程 task 名。")

    @model_validator(mode="after")
    def _validate_duty_range(self) -> Models:
        """校验占空比上下限的前后关系。

        Returns:
            Models: 校验通过后的模型实例。

        Raises:
            ValueError: 下限不小于上限时。
        """
        if self.duty_min >= self.duty_max:
            raise ValueError(
                f"duty_min ({self.duty_min}) 须小于 duty_max ({self.duty_max})"
            )
        return self

    @model_validator(mode="after")
    def _validate_graph(self) -> Models:
        """校验节点名唯一性与 sources 连线规则。

        Returns:
            Models: 校验通过后的模型实例。

        Raises:
            ValueError: 节点名重复、source 指向未知节点，或 mux 与非 mux 的 key 规则违反时。
        """
        names = [n.name for n in self.nodes]
        if len(names) != len(set(names)):
            dup = {x for x in names if names.count(x) > 1}
            raise ValueError(f"nodes.name 须唯一，重复: {sorted(dup)}")

        known = set(names)
        for node in self.nodes:
            for src in node.sources:
                if src.name not in known:
                    raise ValueError(
                        f"节点 {node.name!r} 的 source.name {src.name!r} "
                        f"不在 nodes 的 name 集合中"
                    )
                if node.kind == "mux":
                    if not src.key:
                        raise ValueError(
                            f"mux 节点 {node.name!r} 的每条 source 须提供非空 key"
                        )
                else:
                    if src.key:
                        raise ValueError(
                            f"节点 {node.name!r} kind={node.kind!r} 的 source.key 须为空"
                        )
            if node.kind != "mux" and len(node.sources) > 1:
                raise ValueError(
                    f"非 mux 节点 {node.name!r} 至多允许一条 source（关联数组空键仅容纳一项）"
                )
            if node.kind == "mux":
                keys = [s.key for s in node.sources]
                if len(keys) != len(set(keys)):
                    raise ValueError(f"mux 节点 {node.name!r} 的 source.key 不得重复")
            for hz in node.frequencies:
                if hz < 1:
                    raise ValueError(
                        f"节点 {node.name!r} 的 frequencies 项 {hz} 须为正整数 Hz"
                    )
        return self

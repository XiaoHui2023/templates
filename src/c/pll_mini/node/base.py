from __future__ import annotations

import re
from typing import Any, ClassVar, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from reg_paths import (
    primary_output_group,
)

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _coerce_optional_source_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    raise ValueError("前级引用应为字符串或省略")


def _coerce_required_freq(value: Any) -> int:
    if value is None or value == "":
        raise ValueError("须填写 freq")
    return int(value)


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


class NodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(..., min_length=1, description="节点插件名")

    constraint_fields: ClassVar[dict[str, tuple[str, ...]]] = {}

    def constraint_paths(self, rule: str) -> tuple[str, ...]:
        """将插件声明的约束来源转换为输入字段路径。"""
        local_rule = rule.removeprefix(self.name + "__")
        for prefix, fields in self.constraint_fields.items():
            if local_rule.startswith(prefix):
                return tuple(
                    field
                    if field.startswith("settings.")
                    else f"nodes[{self.name!r}].{field}"
                    for field in fields
                )
        return (
            (f"nodes[{self.name!r}].source",)
            if self.input_refs()
            else (f"nodes[{self.name!r}]",)
        )

    is_target: ClassVar[bool] = False
    is_anchor: ClassVar[bool] = False
    independent_outputs: ClassVar[bool] = False
    plan_priority: ClassVar[int] = 0
    plan_group: ClassVar[str] = ""

    def input_refs(self) -> dict[str, str]:
        """返回输入键与上游引用，单输入使用空键。"""
        source = getattr(self, "source", "")
        if isinstance(source, dict):
            return {str(key): raw for key, raw in source.items()}
        return {"": source} if source else {}

    def selected_input(self, model=None) -> str | None:
        """返回当前选中的输入引用。"""
        return self.input_refs().get("")

    def input_condition(self, builder, key: str) -> str:
        """默认输入无需选择条件。"""
        return "true"

    def fixed_hz(self, group: str = "") -> int | None:
        """返回配置中固定的端口频率。"""
        return self.freq if isinstance(self.freq, int) else None

    def add_constraints(self, builder) -> None:
        """生成节点约束；新插件必须显式提供频率行为。"""
        raise NotImplementedError(f"{self.kind}: add_constraints is required")

    def read_solution(self, builder, raw, model) -> None:
        """读取插件自有求解变量。"""

    def control_encodings(self, builder) -> dict[str, tuple[str, str]]:
        """返回寄存器角色对应的路径与硬件编码表达式。"""
        return {}

    def resolved_values(self, model) -> dict[str, object]:
        """返回寄存器规划需要的节点状态。"""
        return {}

    def fit(self, tree, model, settings) -> None:
        """在图频率确定后补齐器件参数。"""

    def verify(self, tree, model, tolerance: float) -> list:
        """独立回放节点频率关系。"""
        return []

    def static_hz(self, tree, model, group: str, upstream) -> int:
        """回放未求解路径上的固定频率。"""
        fixed = self.fixed_hz(group)
        if fixed is not None:
            return fixed
        raw = self.selected_input(model)
        return upstream(raw) if raw else 0

    def plan_patches(self, index, settings, resolved) -> list:
        """返回节点需要写入的寄存器字段。"""
        return []

    def build_plan_group(self, tree, index, resolved):
        """构建需要多节点共同归并的配置函数。"""
        return None

    _name: str = PrivateAttr(default="")

    @computed_field(  # type: ignore[prop-decorator]
        description="等于 Tree.nodes 字典键；YAML 体内与 model_validate 不可传入。",
    )
    @property
    def name(self) -> str:
        return self._name

    @computed_field(  # type: ignore[prop-decorator]
        description="多路输出名列表；单路节点为空；YAML 不可传入。",
    )
    @property
    def output_groups(self) -> List[str]:
        return []

    @computed_field(  # type: ignore[prop-decorator]
        description="多路输出时为首路输出名，单路为空字符串；YAML 不可传入。",
    )
    @property
    def primary_output_group(self) -> str:
        return primary_output_group(self)

    path: str = Field(
        "",
        description="RTL 层次路径，按 `.` 分隔；pll_mini 仅接受，不参与求解与生成。",
    )
    exclude: bool = Field(default=False, description="排除该节点，不参与求解和配置")
    freq: Optional[int] = Field(
        default=None,
        description="可选频率锚点，单位 Hz；省略表示该节点不主动约束频率。",
    )

    @field_validator("freq", mode="before")
    @classmethod
    def _coerce_node_freq(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        return _coerce_optional_int(value)

    @model_validator(mode="after")
    def _validate_node_freq(self) -> NodeBase:
        if isinstance(self.freq, int) and self.freq <= 0:
            raise ValueError(f"节点 {self.name!r} freq 若填写须大于 0")
        return self


def _validation_node_name(node: NodeBase, info: ValidationInfo) -> str:
    key = (info.context or {}).get("node_name")
    if isinstance(key, str) and key:
        return key
    if node._name:
        return node._name
    raise ValueError("节点须在 Tree.nodes 字典键上下文内校验")

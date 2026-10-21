from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field, field_validator, model_validator

from schema_error import ERR

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_PORT_KEY = re.compile(r"^[A-Za-z0-9_]+$")
_ENDPOINT = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<output>[^\]]+)\])?$")


def _require_sv_id(value: str, *, field: str) -> str:
    if not _SV_ID.match(value):
        raise ValueError(f"{ERR.field(field)} {value!r} 须为合法 SystemVerilog 名字")
    return value


def _require_port_key(value: str, *, field: str) -> str:
    """Validate a rendered port key without imposing an SV identifier shape.

    Numeric keys are valid labels for indexed ports. They are rendered only
    into strings and generated macro suffixes.
    """
    if not _PORT_KEY.match(value):
        raise ValueError(f"{ERR.field(field)} {value!r} 须为非空字母数字端口键")
    return value


def _validate_dot_path(value: str, *, field: str) -> str:
    if not value:
        raise ValueError(f"{ERR.field(field)} 不得为空")
    for part in value.split("."):
        _require_sv_id(part, field=field)
    return value


def _sv_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "1'b1" if value else "1'b0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    raise ValueError(f"属性值 {value!r} 须为 bool、int、float 或 str")


@dataclass(frozen=True)
class SourceRef:
    name: str
    output: str = ""
    input_key: str = ""


@dataclass(frozen=True)
class SvNodeSlot:
    node_key: str
    output: str
    access: str


@dataclass(frozen=True)
class SvPortSlot:
    node_key: str
    output: str
    access: str
    role: str
    port_key: str
    path: str
    instance_name: str
    force_macro: str
    path_macro: str
    disable_macro_suffix: str


SourceValue = Optional[Union[str, Dict[str, str]]]


class Node(BaseModel):
    """Plugin-neutral graph, port, property and register declaration."""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(..., min_length=1, description="SV 插件类名")
    present: bool = Field(default=True, description="是否生成该节点实例")
    source: SourceValue = Field(default=None, description="默认或具名上游节点引用")
    outputs: List[str] = Field(default_factory=list, description="需要展开为数组实例的输出组")
    path: Optional[str] = Field(default=None, description="无功能端点的观测路径")
    in_path: Optional[str] = Field(default=None, description="默认输入端口路径")
    out_path: Optional[str] = Field(default=None, description="默认输出端口路径")
    in_paths: Dict[str, str] = Field(default_factory=dict, description="具名输入端口路径")
    out_paths: Dict[str, str] = Field(default_factory=dict, description="具名输出端口路径")
    reg: Optional[str] = Field(default=None, description="默认寄存器字段路径")
    regs: Dict[str, str] = Field(default_factory=dict, description="具名寄存器字段路径")
    output_regs: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="按输出组覆盖的寄存器字段")
    properties: Dict[str, Any] = Field(default_factory=dict, description="写入全部实例的插件属性")
    output_properties: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="写入指定输出实例的插件属性")

    _name: str = PrivateAttr(default="")

    @field_validator("kind")
    @classmethod
    def _kind_is_sv_type(cls, value: str) -> str:
        return _require_sv_id(value, field="kind")

    @field_validator("outputs")
    @classmethod
    def _outputs_are_unique_ids(cls, value: List[str]) -> List[str]:
        seen: set[str] = set()
        for item in value:
            _require_sv_id(item, field="outputs")
            if item in seen:
                raise ValueError(f"{ERR.field('outputs')} 含重复输出 {item!r}")
            seen.add(item)
        return value

    @field_validator("path", "in_path", "out_path")
    @classmethod
    def _path_is_dot_path(cls, value: Optional[str], info: Any) -> Optional[str]:
        return None if value is None else _validate_dot_path(value, field=info.field_name)

    @field_validator("in_paths", "out_paths")
    @classmethod
    def _path_map_is_valid(cls, value: Dict[str, str], info: Any) -> Dict[str, str]:
        for key, path in value.items():
            _require_port_key(str(key), field=info.field_name)
            _validate_dot_path(path, field=info.field_name)
        return {str(key): path for key, path in value.items()}

    @field_validator("source")
    @classmethod
    def _source_is_valid(cls, value: SourceValue) -> SourceValue:
        if value is None or value == "":
            return None
        items = value.items() if isinstance(value, dict) else [("", value)]
        for key, endpoint in items:
            if key:
                _require_port_key(str(key), field="source")
            if not isinstance(endpoint, str) or not _ENDPOINT.match(endpoint.strip()):
                raise ValueError(f"{ERR.field('source')} 前级引用 {endpoint!r} 须为器件名或器件名[输出名]")
        return value

    @model_validator(mode="after")
    def _normalize_properties(self) -> "Node":
        core = set(type(self).model_fields)
        extras = self.__pydantic_extra__ or {}
        merged = dict(self.properties)
        for key, value in extras.items():
            if key not in core:
                _require_sv_id(key, field="properties")
                if key in merged:
                    raise ValueError(f"{ERR.field('properties')} 与顶层属性重复: {key!r}")
                merged[key] = value
        for key, value in merged.items():
            _require_sv_id(key, field="properties")
            _sv_literal(value)
        for output, values in self.output_properties.items():
            _require_sv_id(output, field="output_properties")
            for key, value in values.items():
                _require_sv_id(key, field="output_properties")
                _sv_literal(value)
        return self

    @computed_field
    @property
    def name(self) -> str:
        return self._name

    @computed_field
    @property
    def output_groups(self) -> List[str]:
        return list(self.outputs)

    @computed_field
    @property
    def sv_is_array(self) -> bool:
        return bool(self.output_groups)

    @computed_field
    @property
    def sources(self) -> List[SourceRef]:
        if self.source is None:
            return []
        entries = self.source.items() if isinstance(self.source, dict) else [("", self.source)]
        result: List[SourceRef] = []
        for key, raw in entries:
            match = _ENDPOINT.match(str(raw).strip())
            assert match is not None
            result.append(SourceRef(match.group("name"), match.group("output") or "", str(key)))
        return result

    @computed_field
    @property
    def common_assignments(self) -> List[tuple[str, str]]:
        values = dict(self.properties)
        for key, value in (self.__pydantic_extra__ or {}).items():
            if key not in type(self).model_fields:
                values.setdefault(key, value)
        return [(key, _sv_literal(value)) for key, value in sorted(values.items())]

    def assignments_for_output(self, output: str) -> List[tuple[str, str]]:
        """Return literal assignments for one generated node instance.

        Args:
            output: Optional output group for an array-backed node.

        Returns:
            Common assignments followed by output-local assignments.
        """
        values = list(self.common_assignments)
        values.extend((key, _sv_literal(value)) for key, value in sorted(self.output_properties.get(output, {}).items()))
        return values

    @computed_field
    @property
    def sv_assignments_by_output(self) -> Dict[str, List[tuple[str, str]]]:
        """Expose rendered assignments without requiring Jinja method calls."""
        outputs = self.output_groups or [""]
        return {output: self.assignments_for_output(output) for output in outputs}

    def regs_for_output(self, output: str) -> Dict[str, str]:
        values = dict(self.regs)
        if self.reg:
            values.setdefault("reg", self.reg)
        values.update(self.output_regs.get(output, {}))
        return values

    @computed_field
    @property
    def port_paths(self) -> List[tuple[str, str, str]]:
        ports: List[tuple[str, str, str]] = []
        if self.path:
            ports.append(("tap", "default", self.path))
        if self.in_path:
            ports.append(("in", "default", self.in_path))
        if self.out_path:
            ports.append(("out", "default", self.out_path))
        ports.extend(("in", key, path) for key, path in self.in_paths.items())
        ports.extend(("out", key, path) for key, path in self.out_paths.items())
        return ports


class Tree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: Dict[str, Node] = Field(description="按输入顺序保存的通用节点声明")

    @model_validator(mode="after")
    def _name_nodes(self) -> "Tree":
        for name, node in self.nodes.items():
            _require_sv_id(name, field="nodes")
            node._name = name
        return self

    @computed_field
    @property
    def nodes_ordered(self) -> List[Node]:
        return [node for node in self.nodes.values() if node.present]

    @computed_field
    @property
    def sv_nodes_ordered(self) -> List[Node]:
        """Return the present nodes in source declaration order for templates."""
        return self.nodes_ordered

    @computed_field
    @property
    def sv_slots(self) -> List[SvNodeSlot]:
        slots: List[SvNodeSlot] = []
        for node in self.nodes_ordered:
            if node.output_groups:
                slots.extend(SvNodeSlot(node.name, output, f'{node.name}["{output}"]') for output in node.output_groups)
            else:
                slots.append(SvNodeSlot(node.name, "", node.name))
        return slots

    @computed_field
    @property
    def sv_node_names(self) -> set[str]:
        return {node.name for node in self.nodes_ordered}

    @computed_field
    @property
    def connectable_slots(self) -> List[SvPortSlot]:
        slots: List[SvPortSlot] = []
        for node in self.nodes_ordered:
            for output in node.output_groups or [""]:
                access = f'{node.name}["{output}"]' if output else node.name
                for role, port_key, path in node.port_paths:
                    suffix = "_".join(item.upper() for item in (node.name, output, role, port_key) if item)
                    instance = "_".join(item for item in (node.name, output, role, port_key) if item)
                    slots.append(SvPortSlot(node.name, output, access, role, port_key, path, instance,
                        f"PATH_DISABLE_{suffix}", suffix, f"_PATH_DISABLE_{suffix}"))
        return slots


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    tree = Tree(nodes=nodes)
    present = tree.sv_node_names
    for node in tree.nodes_ordered:
        for source in node.sources:
            if source.name not in present:
                raise ValueError(f"节点 {node.name!r} 的 source 引用不存在或未 present: {source.name!r}")
            peer = tree.nodes[source.name]
            if source.output and source.output not in peer.output_groups:
                raise ValueError(f"节点 {node.name!r} 的 source 输出不存在: {source.name}[{source.output}]")

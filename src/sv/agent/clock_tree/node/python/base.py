from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo, computed_field, field_validator, model_validator

from schema_error import ERR

from .config import NodePluginConfig
from .registry import parse_plugin_config

_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_PORT_KEY = re.compile(r"^[A-Za-z0-9_]+$")
_ENDPOINT = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_$]*)(?:\[(?P<output>[^\]]+)\])?$")


def require_sv_id(value: str, *, field: str) -> str:
    """验证一个 SystemVerilog 标识符。

    Args:
        value: 用户提供的名称
        field: 报错中显示的配置字段

    Returns:
        str: 原始名称

    Raises:
        ValueError: 名称不是合法标识符
    """
    if not _SV_ID.match(value):
        raise ValueError(f"{ERR.field(field)} {value!r} 须为合法 SystemVerilog 名字")
    return value


def require_port_key(value: str, *, field: str) -> str:
    """验证端口键。

    Args:
        value: 端口键
        field: 报错中显示的配置字段

    Returns:
        str: 原始端口键

    Raises:
        ValueError: 端口键为空或包含不支持的字符
    """
    if not _PORT_KEY.match(value):
        raise ValueError(f"{ERR.field(field)} {value!r} 须为非空字母数字端口键")
    return value


def validate_dot_path(value: str, *, field: str) -> str:
    """验证层次 SystemVerilog 路径。

    Args:
        value: 点分层次路径
        field: 报错中显示的配置字段

    Returns:
        str: 原始路径

    Raises:
        ValueError: 路径为空或含非法层级名
    """
    if not value:
        raise ValueError(f"{ERR.field(field)} 不得为空")
    for part in value.split("."):
        require_sv_id(part, field=field)
    return value


@dataclass(frozen=True)
class SourceRef:
    """一个解析后的上游引用。"""

    name: str
    output: str = ""
    input_key: str = ""


@dataclass(frozen=True)
class SvNodeSlot:
    """一个展开后的 SV 节点实例。"""

    node_key: str
    output: str
    access: str


@dataclass(frozen=True)
class SvPortSlot:
    """一个需要生成 interface 绑定的端口。"""

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
    """插件无关的图、端口与寄存器声明。"""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(..., min_length=1, description="对应的 SystemVerilog 节点插件名")
    exclude: bool = Field(default=False, description="排除该节点，不生成实例、接口和寄存器绑定")
    source: SourceValue = Field(default=None, description="默认或具名上游节点引用")
    outputs: List[str] = Field(default_factory=list, description="展开为数组实例的输出组")
    path: Optional[str] = Field(default=None, description="无功能端点的观测路径")
    in_path: Optional[str] = Field(default=None, description="默认输入端口路径")
    out_path: Optional[str] = Field(default=None, description="默认输出端口路径")
    in_paths: Dict[str, str] = Field(default_factory=dict, description="具名输入端口路径")
    out_paths: Dict[str, str] = Field(default_factory=dict, description="具名输出端口路径")
    reg: Optional[str] = Field(default=None, description="默认寄存器字段路径")
    regs: Dict[str, str] = Field(default_factory=dict, description="具名寄存器字段路径")
    output_regs: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="按输出组覆盖的寄存器字段")
    output_config: Dict[str, Dict[str, object]] = Field(default_factory=dict, description="按输出组覆盖的插件配置")

    _name: str = PrivateAttr(default="")
    _plugin_config: NodePluginConfig = PrivateAttr()
    _output_plugin_configs: Dict[str, NodePluginConfig] = PrivateAttr(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _kind_is_sv_type(cls, value: str) -> str:
        return require_sv_id(value, field="kind")

    @field_validator("outputs")
    @classmethod
    def _outputs_are_unique_ids(cls, value: List[str]) -> List[str]:
        seen: set[str] = set()
        for item in value:
            require_sv_id(item, field="outputs")
            if item in seen:
                raise ValueError(f"{ERR.field('outputs')} 含重复输出 {item!r}")
            seen.add(item)
        return value

    @field_validator("path", "in_path", "out_path")
    @classmethod
    def _path_is_dot_path(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        return None if value is None else validate_dot_path(value, field=info.field_name)

    @field_validator("in_paths", "out_paths")
    @classmethod
    def _path_map_is_valid(cls, value: Dict[str, str], info: ValidationInfo) -> Dict[str, str]:
        for key, path in value.items():
            require_port_key(str(key), field=info.field_name)
            validate_dot_path(path, field=info.field_name)
        return {str(key): path for key, path in value.items()}

    @field_validator("source")
    @classmethod
    def _source_is_valid(cls, value: SourceValue) -> SourceValue:
        if value is None or value == "":
            return None
        items = value.items() if isinstance(value, dict) else [("", value)]
        for key, endpoint in items:
            if key:
                require_port_key(str(key), field="source")
            if not isinstance(endpoint, str) or not _ENDPOINT.match(endpoint.strip()):
                raise ValueError(f"{ERR.field('source')} 前级引用 {endpoint!r} 须为器件名或器件名[输出名]")
        return value

    def _parse_plugin_values(self, values: Dict[str, object]) -> NodePluginConfig:
        """校验插件属性，避免覆盖公共成员。

        Args:
            values: 节点属性或合并后的输出组属性

        Returns:
            NodePluginConfig: 插件校验后的属性

        Raises:
            ValueError: 属性无效或与公共成员重名
        """
        for field in values:
            if field.startswith("_") or field in type(self).model_fields or hasattr(type(self), field):
                raise ValueError(f"{ERR.field(field)} 不能覆盖节点公共成员")
        config = parse_plugin_config(self.kind, values)
        for field in type(config).model_fields:
            if field in type(self).model_fields or hasattr(type(self), field):
                raise ValueError(f"插件字段 {ERR.field(field)} 与节点公共成员重名")
        return config

    @model_validator(mode="after")
    def _parse_plugin_configs(self) -> "Node":
        """将公共字段之外的顶层属性交给节点插件校验。"""
        values = self.__pydantic_extra__ or {}
        self._plugin_config = self._parse_plugin_values(values)
        self.outputs = self._plugin_config.normalize_outputs(self.outputs)
        unknown_outputs = set(self.output_config) | set(self.output_regs)
        unknown_outputs.difference_update(self.outputs)
        if unknown_outputs:
            raise ValueError(f"输出组不存在: {sorted(unknown_outputs)!r}")
        self._output_plugin_configs = {
            output: self._parse_plugin_values(values | overrides)
            for output, overrides in self.output_config.items()
        }
        return self

    @computed_field
    @property
    def name(self) -> str:
        """返回由父级节点字典键绑定的名称。"""
        return self._name

    @computed_field
    @property
    def output_groups(self) -> List[str]:
        """返回输出组名称。"""
        return list(self.outputs)

    @computed_field
    @property
    def sv_is_array(self) -> bool:
        """返回是否展开为关联数组节点。"""
        return bool(self.output_groups)

    @computed_field
    @property
    def sources(self) -> List[SourceRef]:
        """将输入 source 归一为上游引用列表。"""
        if self.source is None:
            return []
        entries = self.source.items() if isinstance(self.source, dict) else [("", self.source)]
        result: List[SourceRef] = []
        for key, raw in entries:
            match = _ENDPOINT.match(str(raw).strip())
            assert match is not None
            result.append(SourceRef(match.group("name"), match.group("output") or "", str(key)))
        return result

    def assignments_for_output(self, output: str) -> List[tuple[str, str]]:
        """合并节点公共配置与输出组覆盖配置。

        Args:
            output: 输出组名称；非数组节点传空字符串

        Returns:
            list[tuple[str, str]]: 按成员名排序的 SystemVerilog 赋值
        """
        values = dict(self._plugin_config.sv_assignments())
        if output in self._output_plugin_configs:
            values.update(self._output_plugin_configs[output].sv_assignments())
        return sorted(values.items())

    @computed_field
    @property
    def sv_assignments_by_output(self) -> Dict[str, List[tuple[str, str]]]:
        """为每个展开实例提供已整理的成员赋值。"""
        outputs = self.output_groups or [""]
        return {output: self.assignments_for_output(output) for output in outputs}

    def regs_for_output(self, output: str) -> Dict[str, str]:
        """返回一个输出实例使用的寄存器字段。

        Args:
            output: 输出组名称；非数组节点传空字符串

        Returns:
            Dict[str, str]: 按输出组覆盖后的寄存器字段
        """
        values = dict(self.regs)
        if self.reg:
            values.setdefault("reg", self.reg)
        values.update(self.output_regs.get(output, {}))
        return values

    @computed_field
    @property
    def port_paths(self) -> List[tuple[str, str, str]]:
        """返回所有声明了 RTL 路径的端口。"""
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
    """按输入顺序管理节点图与可复用的 SV 展开数据。"""

    model_config = ConfigDict(extra="forbid")

    nodes: Dict[str, Node] = Field(description="按输入顺序保存的通用节点声明")

    @model_validator(mode="after")
    def _name_nodes(self) -> "Tree":
        for name, node in self.nodes.items():
            require_sv_id(name, field="nodes")
            node._name = name
        return self

    @computed_field
    @property
    def nodes_ordered(self) -> List[Node]:
        """返回需要生成的节点，顺序与输入一致。"""
        return [node for node in self.nodes.values() if not node.exclude]

    @computed_field
    @property
    def sv_nodes_ordered(self) -> List[Node]:
        """返回模板使用的已生成节点序列。"""
        return self.nodes_ordered

    @computed_field
    @property
    def sv_slots(self) -> List[SvNodeSlot]:
        """展开所有节点实例访问表达式。"""
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
        """返回会出现在 SV tree 中的节点名。"""
        return {node.name for node in self.nodes_ordered}

    @computed_field
    @property
    def connectable_slots(self) -> List[SvPortSlot]:
        """展开所有需要 RTL interface 的端口。"""
        slots: List[SvPortSlot] = []
        for node in self.nodes_ordered:
            for output in node.output_groups or [""]:
                access = f'{node.name}["{output}"]' if output else node.name
                for role, port_key, path in node._plugin_config.port_paths_for_output(output, node.port_paths):
                    suffix = "_".join(item.upper() for item in (node.name, output, role, port_key) if item)
                    instance = "_".join(item for item in (node.name, output, role, port_key) if item)
                    slots.append(SvPortSlot(node.name, output, access, role, port_key, path, instance,
                        f"PATH_DISABLE_{suffix}", suffix, f"_PATH_DISABLE_{suffix}"))
        return slots


def validate_nodes_graph(nodes: Dict[str, Node]) -> None:
    """验证已生成节点之间的 source 引用。

    Args:
        nodes: 根输入中解析出的节点映射

    Raises:
        ValueError: source 指向不存在、未生成或不存在的输出组
    """
    tree = Tree(nodes=nodes)
    generated = tree.sv_node_names
    for node in tree.nodes_ordered:
        for source in node.sources:
            if source.name not in generated:
                raise ValueError(f"节点 {node.name!r} 的 source 引用不存在或未生成: {source.name!r}")
            peer = tree.nodes[source.name]
            if source.output and source.output not in peer.output_groups:
                raise ValueError(f"节点 {node.name!r} 的 source 输出不存在: {source.name}[{source.output}]")

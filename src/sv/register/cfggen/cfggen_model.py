from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ralf_model import BlockNode, FieldNode, RegisterNode, RalfDocument, SystemNode


class CfgField(BaseModel):
    """One field retained in a generated register configuration class."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Lowercase SystemVerilog member name.")
    width: int = Field(description="Packed member width in bits.")
    value_lsb: int = Field(description="Least-significant position in the normalized value member.")
    value_msb: int = Field(description="Most-significant position in the normalized value member.")


class CfgRegister(BaseModel):
    """One register class after access filtering and bit-range normalization."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Lowercase instance name in the owning block class.")
    class_name: str = Field(description="Generated SystemVerilog class name.")
    ral_type: str = Field(description="Predicted ralgen register class name.")
    value_width: int = Field(description="Normalized value width in bits.")
    reset_literal: str = Field(description="Width-qualified SystemVerilog reset literal.")
    fields: list[CfgField] = Field(description="Fields that remain after access filtering.")


class CfgChild(BaseModel):
    """One register, block, or system member in a generated container class."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Member category: register, block, or system.")
    name: str = Field(description="Lowercase SystemVerilog member name.")
    class_name: str = Field(description="Generated member class name.")
    ral_type: str = Field(description="Predicted ralgen member type name.")
    is_array: bool = Field(description="Whether the member is a fixed unpacked array.")
    count: int = Field(description="Number of elements when the member is an array.")


class CfgContainer(BaseModel):
    """One generated block or system configuration class."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Container category: block or system.")
    name: str = Field(description="Lowercase RALF definition name.")
    class_name: str = Field(description="Generated SystemVerilog class name.")
    ral_type: str = Field(description="Predicted ralgen container type name.")
    children: list[CfgChild] = Field(description="Direct members in declaration order.")


class CfgDesign(BaseModel):
    """Complete dependency-ordered data consumed by the SystemVerilog template."""

    model_config = ConfigDict(extra="forbid")

    guard: str = Field(description="Compilation guard name.")
    base_class: str = Field(description="Base class shared by generated block and system classes.")
    emit_ral_sync_methods: bool = Field(description="Whether RAL synchronization methods are emitted.")
    value_name: str = Field(description="Register value member name.")
    rand_mode_lock_name: str = Field(description="Register random-mode lock member name.")
    reset_value_name: str = Field(description="Register reset parameter name.")
    constraint_name: str = Field(description="Register field-link constraint name.")
    set_ral_method_name: str = Field(description="Method name that copies values into a RAL model.")
    get_ral_method_name: str = Field(description="Method name that copies values from a RAL model.")
    registers: list[CfgRegister] = Field(description="All register classes in dependency-first order.")
    containers: list[CfgContainer] = Field(description="Blocks followed by systems in dependency-first order.")


class _Definition:
    """A named RALF definition retained during reference resolution."""

    def __init__(self, kind: str, type_name: str, node: BlockNode | SystemNode) -> None:
        self.kind = kind
        self.type_name = type_name
        self.node = node


_ARRAY_SUFFIX = re.compile(r"^(?P<name>.+?)\[(?P<count>[0-9]+)\]$")
_SV_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SV_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*$")
_SV_RESERVED = {
    "alias", "always", "always_comb", "always_ff", "always_latch", "and", "assert",
    "assign", "automatic", "begin", "bit", "break", "byte", "case", "class", "clocking",
    "const", "constraint", "continue", "cover", "covergroup", "do", "else", "end",
    "endclass", "endfunction", "endpackage", "endtask", "enum", "extends", "extern",
    "final", "for", "foreach", "forever", "fork", "function", "generate", "if", "import",
    "inout", "input", "inside", "int", "integer", "interface", "local", "localparam",
    "logic", "longint", "modport", "module", "new", "null", "output", "package",
    "packed", "parameter", "priority", "program", "protected", "pure", "rand", "randc",
    "ref", "reg", "repeat", "return", "shortint", "signed", "static", "string", "struct",
    "super", "tagged", "task", "this", "time", "typedef", "union", "unique", "unsigned",
    "var", "virtual", "void", "wait", "while", "wire", "with",
}


def require_sv_identifier(value: str, role: str) -> str:
    """Validate and lowercase a configurable SystemVerilog identifier.

    Args:
        value: Identifier supplied by the configuration.
        role: Configuration field name used in validation errors.

    Returns:
        The lowercase identifier.

    Raises:
        ValueError: The value is not a legal non-reserved identifier.
    """
    lowered = value.lower()
    if not _SV_IDENTIFIER.fullmatch(lowered) or lowered in _SV_RESERVED:
        raise ValueError(f"{role} must be a non-reserved SystemVerilog identifier: {value!r}")
    return lowered


def require_sv_type(value: str, role: str) -> str:
    """Validate a configurable SystemVerilog class type.

    Args:
        value: Type name supplied by the configuration.
        role: Configuration field name used in validation errors.

    Returns:
        The validated type name.

    Raises:
        ValueError: The value is not a class type or package-qualified class type.
    """
    if not _SV_TYPE.fullmatch(value):
        raise ValueError(f"{role} must be a SystemVerilog class type: {value!r}")
    return value


def _sv_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]", "_", value.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise ValueError(f"RALF name has no usable SystemVerilog characters: {value!r}")
    if normalized[0].isdigit():
        normalized = "_" + normalized
    if normalized in _SV_RESERVED:
        normalized += "_"
    return normalized


def _parse_reference(value: str) -> tuple[str, int, bool]:
    match = _ARRAY_SUFFIX.fullmatch(value.strip())
    if match is None:
        if "[" in value or "]" in value:
            raise ValueError(f"only a fixed trailing array count is supported: {value!r}")
        return value.strip(), 1, False
    count = int(match.group("count"))
    if count < 1:
        raise ValueError(f"array count must be positive: {value!r}")
    return match.group("name"), count, True


def _statement_value(field: FieldNode, keyword: str) -> str | None:
    prefix = keyword.lower() + " "
    for statement in field.inner_statements:
        text = statement.strip()
        if text.lower().startswith(prefix) and text.endswith(";"):
            return text[len(prefix) : -1].strip()
    return None


def _parse_reset_literal(text: str | None) -> int:
    if text is None:
        return 0
    compact = text.replace("_", "").strip()
    if any(ch in compact.lower() for ch in ("x", "z", "?")):
        raise ValueError(f"reset value must not contain unknown bits: {text!r}")
    match = re.fullmatch(r"(?:[0-9]+)?'s?([bodh])([0-9a-f]+)", compact, re.IGNORECASE)
    if match is not None:
        base = {"b": 2, "o": 8, "d": 10, "h": 16}[match.group(1).lower()]
        return int(match.group(2), base)
    try:
        return int(compact, 0)
    except ValueError as exc:
        raise ValueError(f"unsupported reset literal: {text!r}") from exc


class CfgDesignBuilder:
    """Resolve a parsed RALF document into configuration classes."""

    def __init__(
        self,
        document: RalfDocument,
        *,
        class_prefix: str,
        base_class: str,
        ignored_field_accesses: set[str],
        emit_ral_sync_methods: bool,
        value_name: str,
        rand_mode_lock_name: str,
        reset_value_name: str,
        constraint_name: str,
        set_ral_method_name: str,
        get_ral_method_name: str,
    ) -> None:
        self.document = document
        self.class_prefix = class_prefix
        self.base_class = base_class
        self.ignored_field_accesses = ignored_field_accesses
        self.emit_ral_sync_methods = emit_ral_sync_methods
        self.value_name = value_name
        self.rand_mode_lock_name = rand_mode_lock_name
        self.reset_value_name = reset_value_name
        self.constraint_name = constraint_name
        self.set_ral_method_name = set_ral_method_name
        self.get_ral_method_name = get_ral_method_name
        self.definitions: dict[tuple[str, str], _Definition] = {}
        self.class_owners: dict[str, str] = {}

    def build(self) -> CfgDesign:
        """Build and validate the complete output model.

        Returns:
            Dependency-ordered register and container class data.

        Raises:
            ValueError: The input has invalid names, layout, references, or dependencies.
        """
        generated_names = [
            self.value_name,
            self.rand_mode_lock_name,
            self.reset_value_name,
            self.constraint_name,
        ]
        if self.emit_ral_sync_methods:
            generated_names.extend([self.set_ral_method_name, self.get_ral_method_name])
        if len(generated_names) != len(set(generated_names)):
            raise ValueError("generated register member names must be unique")

        for block in self.document.blocks:
            self._collect_block(block)
        for system in self.document.systems:
            self._collect_system(system)

        ordered_blocks = self._ordered_definitions("block")
        ordered_systems = self._ordered_definitions("system")
        registers: list[CfgRegister] = []
        containers: list[CfgContainer] = []
        for definition in ordered_blocks:
            container, block_registers = self._build_block(definition)
            registers.extend(block_registers)
            containers.append(container)
        for definition in ordered_systems:
            containers.append(self._build_system(definition))

        guard = _sv_name(self.class_prefix + "classes").upper() + "_SV"
        return CfgDesign(
            guard=guard,
            base_class=self.base_class,
            emit_ral_sync_methods=self.emit_ral_sync_methods,
            value_name=self.value_name,
            rand_mode_lock_name=self.rand_mode_lock_name,
            reset_value_name=self.reset_value_name,
            constraint_name=self.constraint_name,
            set_ral_method_name=self.set_ral_method_name,
            get_ral_method_name=self.get_ral_method_name,
            registers=registers,
            containers=containers,
        )

    def _definition_name(self, node: BlockNode | SystemNode) -> str:
        source = node.rhs_head if node.rhs_head is not None else node.name
        name, _, _ = _parse_reference(source)
        return _sv_name(name)

    def _register_definition(self, kind: str, node: BlockNode | SystemNode) -> None:
        if not node.has_body:
            return
        type_name = self._definition_name(node)
        key = (kind, type_name)
        if key in self.definitions:
            raise ValueError(f"duplicate {kind} definition after lowercase normalization: {type_name}")
        class_name = self._container_class_name(type_name)
        owner = f"{kind} {type_name}"
        previous = self.class_owners.setdefault(class_name, owner)
        if previous != owner:
            raise ValueError(f"generated class name collision: {class_name} ({previous}, {owner})")
        self.definitions[key] = _Definition(kind, type_name, node)

    def _collect_block(self, node: BlockNode) -> None:
        if not node.has_body:
            return
        self._register_definition("block", node)
        for child in node.blocks:
            self._collect_block(child)

    def _collect_system(self, node: SystemNode) -> None:
        if not node.has_body:
            return
        self._register_definition("system", node)
        for child in node.systems:
            self._collect_system(child)
        for child in node.blocks:
            self._collect_block(child)

    def _target(self, kind: str, node: BlockNode | SystemNode) -> _Definition:
        source = node.rhs_head if node.rhs_head is not None else node.name
        target_name, _, _ = _parse_reference(source)
        key = (kind, _sv_name(target_name))
        target = self.definitions.get(key)
        if target is None:
            raise ValueError(f"unresolved {kind} reference: {source!r}")
        return target

    def _ordered_definitions(self, kind: str) -> list[_Definition]:
        ordered: list[_Definition] = []
        state: dict[tuple[str, str], int] = {}

        def visit(definition: _Definition) -> None:
            key = (kind, definition.type_name)
            if state.get(key) == 2:
                return
            if state.get(key) == 1:
                raise ValueError(f"cyclic {kind} reference involving {definition.type_name}")
            state[key] = 1
            if kind == "block":
                node = definition.node
                assert isinstance(node, BlockNode)
                for child in node.blocks:
                    visit(self._target("block", child))
            else:
                node = definition.node
                assert isinstance(node, SystemNode)
                for child in node.systems:
                    visit(self._target("system", child))
                for child in node.blocks:
                    self._target("block", child)
            state[key] = 2
            ordered.append(definition)

        for key, definition in self.definitions.items():
            if key[0] == kind:
                visit(definition)
        return ordered

    def _container_class_name(self, type_name: str) -> str:
        return self.class_prefix + type_name

    def _child(self, kind: str, node: BlockNode | SystemNode) -> CfgChild:
        lhs_name, lhs_count, lhs_array = _parse_reference(node.name)
        source = node.rhs_head if node.rhs_head is not None else node.name
        _, rhs_count, rhs_array = _parse_reference(source)
        if lhs_array and rhs_array and lhs_count != rhs_count:
            raise ValueError(f"conflicting array counts on {node.name!r} and {source!r}")
        target = self._target(kind, node)
        is_array = lhs_array or rhs_array
        count = lhs_count if lhs_array else rhs_count
        return CfgChild(
            kind=kind,
            name=_sv_name(lhs_name),
            class_name=self._container_class_name(target.type_name),
            ral_type=("ral_block_" if kind == "block" else "ral_sys_") + target.type_name,
            is_array=is_array,
            count=count,
        )

    def _build_block(self, definition: _Definition) -> tuple[CfgContainer, list[CfgRegister]]:
        node = definition.node
        assert isinstance(node, BlockNode)
        registers: list[CfgRegister] = []
        children: list[CfgChild] = []
        member_names: set[str] = set()
        for register in node.registers:
            cfg_register = self._build_register(definition.type_name, register)
            if cfg_register is None:
                continue
            self._claim_member(member_names, cfg_register.name, definition.type_name)
            registers.append(cfg_register)
            children.append(
                CfgChild(
                    kind="register",
                    name=cfg_register.name,
                    class_name=cfg_register.class_name,
                    ral_type=cfg_register.ral_type,
                    is_array=False,
                    count=1,
                )
            )
        for child_node in node.blocks:
            child = self._child("block", child_node)
            self._claim_member(member_names, child.name, definition.type_name)
            children.append(child)
        container = CfgContainer(
            kind="block",
            name=definition.type_name,
            class_name=self._container_class_name(definition.type_name),
            ral_type="ral_block_" + definition.type_name,
            children=children,
        )
        return container, registers

    def _build_system(self, definition: _Definition) -> CfgContainer:
        node = definition.node
        assert isinstance(node, SystemNode)
        children: list[CfgChild] = []
        member_names: set[str] = set()
        for child_node in node.systems:
            child = self._child("system", child_node)
            self._claim_member(member_names, child.name, definition.type_name)
            children.append(child)
        for child_node in node.blocks:
            child = self._child("block", child_node)
            self._claim_member(member_names, child.name, definition.type_name)
            children.append(child)
        return CfgContainer(
            kind="system",
            name=definition.type_name,
            class_name=self._container_class_name(definition.type_name),
            ral_type="ral_sys_" + definition.type_name,
            children=children,
        )

    def _claim_member(self, names: set[str], name: str, owner: str) -> None:
        if name in names:
            raise ValueError(f"duplicate member after lowercase normalization in {owner}: {name}")
        names.add(name)

    def _build_register(self, block_name: str, register: RegisterNode) -> CfgRegister | None:
        if register.declaration_only:
            raise ValueError(f"register declaration has no field definition: {block_name}.{register.name}")
        layouts: list[tuple[FieldNode, int, int, str, int]] = []
        cursor = 0
        for field in register.fields:
            width_text = _statement_value(field, "bits")
            width = int(width_text, 0) if width_text is not None else 1
            if width < 1:
                raise ValueError(f"field width must be positive: {block_name}.{register.name}.{field.name}")
            lsb = field.offset_bits if field.offset_bits is not None else cursor
            if lsb < 0:
                raise ValueError(f"field offset must be nonnegative: {block_name}.{register.name}.{field.name}")
            access = (_statement_value(field, "access") or "rw").lower()
            reset = _parse_reset_literal(_statement_value(field, "reset"))
            layouts.append((field, lsb, width, access, reset))
            cursor = max(cursor, lsb + width)

        included = [item for item in layouts if item[3] not in self.ignored_field_accesses]
        if not included:
            return None
        reg_lsb = min(item[1] for item in included)
        reg_msb = max(item[1] + item[2] - 1 for item in included)
        value_width = reg_msb - reg_lsb + 1
        occupied: set[int] = set()
        field_names: set[str] = set()
        fields: list[CfgField] = []
        reset_value = 0
        reserved_members = {
            self.value_name,
            self.rand_mode_lock_name,
            self.reset_value_name,
            self.constraint_name,
        }
        if self.emit_ral_sync_methods:
            reserved_members.update({self.set_ral_method_name, self.get_ral_method_name})
        for field, lsb, width, _access, reset in included:
            positions = set(range(lsb, lsb + width))
            if occupied & positions:
                raise ValueError(f"overlapping included fields in {block_name}.{register.name}")
            occupied.update(positions)
            name = _sv_name(field.name)
            if name in reserved_members:
                raise ValueError(
                    f"field name collides with a generated register member in "
                    f"{block_name}.{register.name}: {name}"
                )
            self._claim_member(field_names, name, f"{block_name}.{register.name}")
            value_lsb = lsb - reg_lsb
            fields.append(
                CfgField(
                    name=name,
                    width=width,
                    value_lsb=value_lsb,
                    value_msb=value_lsb + width - 1,
                )
            )
            reset_value |= (reset & ((1 << width) - 1)) << value_lsb

        register_name = _sv_name(register.name)
        class_name = self.class_prefix + block_name + "_" + register_name
        owner = f"register {block_name}.{register_name}"
        previous = self.class_owners.setdefault(class_name, owner)
        if previous != owner:
            raise ValueError(f"generated class name collision: {class_name} ({previous}, {owner})")
        digits = max(1, (value_width + 3) // 4)
        return CfgRegister(
            name=register_name,
            class_name=class_name,
            ral_type=f"ral_reg_{block_name}_{register_name}",
            value_width=value_width,
            reset_literal=f"{value_width}'h{reset_value:0{digits}x}",
            fields=fields,
        )


def resolve_input_path(value: str, family_dir: Path) -> Path:
    """Resolve a RALF input path.

    Args:
        value: Absolute or relative input path.
        family_dir: Template family directory used as the final relative-path base.

    Returns:
        The resolved existing file path.

    Raises:
        ValueError: No candidate path identifies a file.
    """
    path = Path(value)
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, family_dir / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = ", ".join(str(candidate.resolve()) for candidate in candidates)
    raise ValueError(f"RALF file not found: {value!r}; searched: {searched}")

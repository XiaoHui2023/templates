from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cfggen_model import (
    CfgDesign,
    CfgDesignBuilder,
    require_sv_identifier,
    require_sv_type,
    resolve_input_path,
)
from ralf_model import load_ralf_file


class Models(BaseModel):
    """Configuration for converting one top-level RALF source into SV configuration classes."""

    model_config = ConfigDict(extra="ignore")

    ralf_file: str = Field(description="Top-level RALF file path.")
    include_dirs: list[str] = Field(
        default_factory=list,
        description="Additional directories used by RALF source statements.",
    )
    encoding: str = Field("utf-8", description="Text encoding used for every RALF source file.")
    class_prefix: str = Field("cfg_", min_length=1, description="Prefix added to every generated class name.")
    base_class: str = Field("uvm_sequence_item", description="Base class shared by block and system classes.")
    ignored_field_accesses: list[str] = Field(
        default_factory=lambda: ["ro"],
        description="Lowercase field access names omitted from generated classes.",
    )
    emit_ral_sync_methods: bool = Field(
        False,
        description="Adds methods that copy values to and from ralgen register-model objects.",
    )
    value_name: str = Field("value", description="Register packed-value member name.")
    rand_mode_lock_name: str = Field("rand_mode_locked", description="Register random-mode lock member name.")
    reset_value_name: str = Field("reset_value", description="Register reset parameter name.")
    constraint_name: str = Field("_cst", description="Constraint name that links fields to the packed value.")
    set_ral_method_name: str = Field("set_ral_value", description="Method name for copying values into a register model.")
    get_ral_method_name: str = Field("get_ral_value", description="Method name for copying values from a register model.")

    @field_validator("class_prefix", mode="before")
    @classmethod
    def validate_class_prefix(cls, value: object) -> str:
        """Normalize and validate the class prefix."""
        if not isinstance(value, str):
            raise ValueError("class_prefix must be a string")
        lowered = value.lower()
        if not lowered or not lowered.isascii() or not lowered.replace("_", "a").isalnum() or lowered[0].isdigit():
            raise ValueError("class_prefix must be a lowercase-compatible SystemVerilog name prefix")
        return lowered

    @field_validator("base_class")
    @classmethod
    def validate_base_class(cls, value: str) -> str:
        """Validate the shared SystemVerilog base class type."""
        return require_sv_type(value, "base_class")

    @field_validator(
        "value_name",
        "rand_mode_lock_name",
        "reset_value_name",
        "constraint_name",
        "set_ral_method_name",
        "get_ral_method_name",
    )
    @classmethod
    def validate_identifier(cls, value: str, info) -> str:
        """Normalize and validate configurable generated identifiers."""
        return require_sv_identifier(value, info.field_name)

    @field_validator("ignored_field_accesses")
    @classmethod
    def normalize_ignored_accesses(cls, value: list[str]) -> list[str]:
        """Normalize access names and remove duplicates without changing order."""
        normalized: list[str] = []
        for item in value:
            access = item.strip().lower()
            if not access:
                raise ValueError("ignored_field_accesses must not contain an empty name")
            if access not in normalized:
                normalized.append(access)
        return normalized

    @property
    def design(self) -> CfgDesign:
        """Load the RALF tree and expose the complete dependency-ordered output model."""
        family_dir = Path(__file__).resolve().parent
        ralf_path = resolve_input_path(self.ralf_file, family_dir)
        include_paths = []
        for value in self.include_dirs:
            path = Path(value)
            include_paths.append(path.resolve() if path.is_absolute() else (ralf_path.parent / path).resolve())
        document = load_ralf_file(
            ralf_path,
            encoding=self.encoding,
            include_paths=include_paths,
        )
        builder = CfgDesignBuilder(
            document,
            class_prefix=self.class_prefix,
            base_class=self.base_class,
            ignored_field_accesses=set(self.ignored_field_accesses),
            emit_ral_sync_methods=self.emit_ral_sync_methods,
            value_name=self.value_name,
            rand_mode_lock_name=self.rand_mode_lock_name,
            reset_value_name=self.reset_value_name,
            constraint_name=self.constraint_name,
            set_ral_method_name=self.set_ral_method_name,
            get_ral_method_name=self.get_ral_method_name,
        )
        return builder.build()

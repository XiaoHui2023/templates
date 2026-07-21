from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field(
        "Connection",
        min_length=1,
        description="PascalCase prefix for generated symbols. The interface name is '<class_prefix>interface'.",
    )
    default_data_width: int = Field(
        1,
        ge=1,
        description="Default value for the DW interface parameter.",
    )
    default_latency: float = Field(
        5.0,
        ge=0.0,
        description="Default value for the LATENCY interface parameter, measured in time_unit.",
    )
    time_unit: str = Field(
        "1ns",
        description="SystemVerilog timeunit used by the interface.",
    )
    time_precision: str = Field(
        "1ps",
        description="SystemVerilog timeprecision used by the interface.",
    )
    check_enable_default: bool = Field(
        False,
        description="Initial runtime value of check_enable.",
    )

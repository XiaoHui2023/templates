from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SV_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SV_TYPE = re.compile(r"^([A-Za-z_][A-Za-z0-9_$]*::)*[A-Za-z_][A-Za-z0-9_$]*$")


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field(
        "dw_spi_",
        min_length=1,
        description="Type name prefix joined with fixed suffixes.",
    )
    regmodel_type: str = Field(
        "dw_spi_regmodel",
        description="SystemVerilog type used for the DesignWare SPI register model handle in settings.",
    )
    ssi_variant: Literal["PSSI", "HSSI"] = Field(
        "PSSI",
        description="DesignWare SSI register-layout family used by controller-facing flows.",
    )
    default_io_lanes: Literal[1, 2, 4] = Field(
        4,
        description="Default SPI data lanes used by per-transfer configuration constraints.",
    )
    default_speed_multiplier: Literal[1, 2, 4] = Field(
        4,
        description="Default transfer-rate multiplier used by per-transfer configuration constraints.",
    )
    default_frame_mode: Literal["STANDARD", "ENHANCED"] = Field(
        "ENHANCED",
        description="Default standard/enhanced transfer mode used by per-transfer configuration constraints.",
    )
    default_data_frame_bits: int = Field(
        8,
        ge=4,
        le=32,
        description="Default data frame size used by per-transfer configuration constraints.",
    )
    num_cs: int = Field(
        4,
        ge=1,
        le=32,
        description="Number of chip-select lines available to generated transfers.",
    )
    default_spi_mode: int = Field(
        0,
        ge=0,
        le=3,
        description="Default Motorola SPI clock mode used by kit convenience tasks.",
    )
    default_cs: int = Field(
        0,
        ge=0,
        description="Default chip-select index used by kit convenience tasks.",
    )
    default_addr_bytes: Literal[3, 4] = Field(
        3,
        description="Default flash address phase width in bytes.",
    )
    default_rw_data_bytes: int = Field(
        256,
        ge=1,
        le=1_048_576,
        description="Default byte count randomized by rw_test when write_data is empty.",
    )
    target_sclk_hz: int = Field(
        6_000_000,
        ge=1,
        description="Target SPI serial output frequency used to derive BAUDR from measured ssi_clk.",
    )
    fifo_depth_bytes: int = Field(
        32,
        ge=1,
        le=4096,
        description="DesignWare SPI FIFO depth in bytes.",
    )
    min_hclk_hz: int = Field(
        24_000_000,
        ge=1,
        description="Minimum hclk frequency accepted by clock check sequences.",
    )
    min_ssi_clk_hz: int = Field(
        24_000_000,
        ge=1,
        description="Minimum controller ssi_clk frequency accepted by clock check sequences.",
    )
    clock_check_tolerance_ppm: int = Field(
        10_000,
        ge=0,
        le=1_000_000,
        description="Default tolerance used by clock check sequences.",
    )
    interrupt_timeout_ssi_clk_cycles: int = Field(
        1_000_000,
        ge=1,
        description="Maximum ssi_clk cycles to wait for intr before transfer sequences fatal.",
    )
    default_tx_fifo_threshold: int = Field(
        0,
        ge=0,
        le=255,
        description="Default transmit FIFO threshold used by register configuration tasks.",
    )
    default_rx_fifo_threshold: int = Field(
        0,
        ge=0,
        le=255,
        description="Default receive FIFO threshold used by register configuration tasks.",
    )
    default_rx_sample_delay_ns: int = Field(
        0,
        ge=0,
        description="Default receive sample delay value written when nonzero.",
    )
    support_rx_sample_delay: bool = Field(
        True,
        description="Allow transfers to request receive sample delay.",
    )
    internal_dma: bool = Field(
        False,
        description="Generate internal DMA register programming and built-in DMA mover support.",
    )
    external_dma: bool = Field(
        False,
        description="Generate external DMA request register programming support.",
    )
    support_master: bool = Field(
        True,
        description="Allow master-mode transfers.",
    )
    support_slave: bool = Field(
        True,
        description="Allow slave-mode transfers.",
    )
    support_standard: bool = Field(
        True,
        description="Allow standard SSI transfers.",
    )
    support_enhanced: bool = Field(
        True,
        description="Allow enhanced SPI transfers with instruction, address, and dummy phases.",
    )
    support_general_spi: bool = Field(
        True,
        description="Allow non-flash SPI peripheral traffic.",
    )
    support_flash_spi: bool = Field(
        True,
        description="Allow SPI flash style traffic.",
    )
    memh_max_bytes_per_line: int = Field(
        16,
        ge=1,
        le=256,
        description="Maximum consecutive data bytes emitted on one memh line.",
    )

    @field_validator("class_prefix")
    @classmethod
    def _validate_class_prefix(cls, value: str) -> str:
        if not _SV_IDENTIFIER.match(value):
            raise ValueError(f"class_prefix {value!r} must be a SystemVerilog identifier prefix")
        return value

    @field_validator("regmodel_type")
    @classmethod
    def _validate_regmodel_type(cls, value: str) -> str:
        if not _SV_TYPE.match(value):
            raise ValueError(f"regmodel_type {value!r} must be a SystemVerilog type identifier")
        return value

    @model_validator(mode="after")
    def _validate_enabled_modes(self) -> Models:
        if not self.support_master and not self.support_slave:
            raise ValueError("at least one of support_master or support_slave must be enabled")
        if not self.support_standard and not self.support_enhanced:
            raise ValueError("at least one of support_standard or support_enhanced must be enabled")
        if not self.support_general_spi and not self.support_flash_spi:
            raise ValueError("at least one of support_general_spi or support_flash_spi must be enabled")
        if self.internal_dma and self.external_dma:
            raise ValueError("internal_dma and external_dma cannot both be enabled")
        return self

    @model_validator(mode="after")
    def _validate_default_cs(self) -> Models:
        if self.default_cs >= self.num_cs:
            raise ValueError("default_cs must be less than num_cs")
        return self

    @model_validator(mode="after")
    def _validate_transfer_defaults(self) -> Models:
        if self.default_frame_mode == "STANDARD" and self.default_speed_multiplier != 1:
            raise ValueError("default_speed_multiplier must be 1 when default_frame_mode is STANDARD")
        if self.default_speed_multiplier > 1 and self.default_frame_mode != "ENHANCED":
            raise ValueError("default_frame_mode must be ENHANCED when default_speed_multiplier is greater than 1")
        if self.default_frame_mode == "STANDARD" and not self.support_standard:
            raise ValueError("default_frame_mode STANDARD requires support_standard")
        if self.default_frame_mode == "ENHANCED" and not self.support_enhanced:
            raise ValueError("default_frame_mode ENHANCED requires support_enhanced")
        return self

    @model_validator(mode="after")
    def _validate_fifo_thresholds(self) -> Models:
        if self.default_tx_fifo_threshold >= self.fifo_depth_bytes:
            raise ValueError("default_tx_fifo_threshold must be less than fifo_depth_bytes")
        if self.default_rx_fifo_threshold >= self.fifo_depth_bytes:
            raise ValueError("default_rx_fifo_threshold must be less than fifo_depth_bytes")
        return self

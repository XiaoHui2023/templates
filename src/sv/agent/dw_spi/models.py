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
    max_io_lanes: Literal[1, 2, 4] = Field(
        4,
        description="Maximum SPI data lanes supported by the generated agent configuration.",
    )
    max_speed_multiplier: Literal[1, 2, 4, 8] = Field(
        4,
        description="Maximum transfer-rate multiplier supported by the generated agent configuration.",
    )
    ssi_variant: Literal["PSSI", "HSSI"] = Field(
        "PSSI",
        description="DesignWare SSI register-layout family used by controller-facing flows.",
    )
    max_data_frame_bits: Literal[8, 16, 32] = Field(
        32,
        description="Maximum data frame size accepted by transfer constraints.",
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
    default_baud_div: int = Field(
        2,
        ge=2,
        le=65534,
        description="Default even serial clock divider written to BAUDR by register configuration tasks.",
    )
    fifo_depth_bytes: int = Field(
        32,
        ge=1,
        le=4096,
        description="DesignWare SPI FIFO depth in bytes.",
    )
    input_clock_hz: int = Field(
        12_000_000,
        ge=1,
        description="Input clock frequency used to validate the default BAUDR divider.",
    )
    max_output_hz: int = Field(
        6_000_000,
        ge=1,
        description="Maximum allowed SPI output frequency after BAUDR division.",
    )
    clock_check_tolerance_ppm: int = Field(
        50_000,
        ge=0,
        le=1_000_000,
        description="Default tolerance used by clock check sequences.",
    )
    clock_check_sample_edges: int = Field(
        4,
        ge=2,
        le=1024,
        description="Default number of rising edges sampled when measuring a clock.",
    )
    clock_check_timeout_ns: int = Field(
        1_000_000,
        ge=1,
        description="Default timeout in ns used by clock measurement tasks.",
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
    support_dma: bool = Field(
        True,
        description="Allow transfers to mark DMA-backed movement.",
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
    flash_size_bytes: int = Field(
        16 * 1024 * 1024,
        ge=1,
        le=2**31 - 1,
        description="Addressable flash-model size in bytes.",
    )
    flash_page_size: int = Field(
        256,
        ge=1,
        le=4096,
        description="Page-program chunk size used by flash write flows.",
    )
    flash_erase_value: int = Field(
        0xFF,
        ge=0,
        le=0xFF,
        description="Byte value used for unprogrammed flash memory.",
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
        return self

    @model_validator(mode="after")
    def _validate_flash_page_size(self) -> Models:
        if self.flash_page_size > self.flash_size_bytes:
            raise ValueError("flash_page_size must not exceed flash_size_bytes")
        return self

    @model_validator(mode="after")
    def _validate_default_cs(self) -> Models:
        if self.default_cs >= self.num_cs:
            raise ValueError("default_cs must be less than num_cs")
        return self

    @model_validator(mode="after")
    def _validate_baud_div_even(self) -> Models:
        if self.default_baud_div % 2:
            raise ValueError("default_baud_div must be even")
        return self

    @model_validator(mode="after")
    def _validate_baud_output_limit(self) -> Models:
        if self.input_clock_hz > self.max_output_hz * self.default_baud_div:
            raise ValueError("input_clock_hz / default_baud_div must not exceed max_output_hz")
        return self

    @model_validator(mode="after")
    def _validate_fifo_thresholds(self) -> Models:
        if self.default_tx_fifo_threshold >= self.fifo_depth_bytes:
            raise ValueError("default_tx_fifo_threshold must be less than fifo_depth_bytes")
        if self.default_rx_fifo_threshold >= self.fifo_depth_bytes:
            raise ValueError("default_rx_fifo_threshold must be less than fifo_depth_bytes")
        return self

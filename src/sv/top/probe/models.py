from __future__ import annotations

import re
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


_SV_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _macro_suffix(name: str) -> str:
    return name.upper().replace("$", "_")


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., min_length=1)
    freq: int = Field(0, ge=0)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefix: str = Field("probe_", min_length=1)
    tolerance_ppm: int = Field(20000, ge=0)
    min_freq_hz: int = Field(15000, ge=1)
    stable_cycles: int = Field(5, ge=1)

    @field_validator("prefix")
    @classmethod
    def _validate_prefix(cls, value: str) -> str:
        if not _SV_IDENT.match(value + "x"):
            raise ValueError("settings.prefix must form valid SystemVerilog identifiers")
        return value


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: Dict[str, Signal] = Field(..., min_length=1)
    settings: Settings = Field(default_factory=Settings)

    @field_validator("signals")
    @classmethod
    def _validate_signal_names(cls, value: Dict[str, Signal]) -> Dict[str, Signal]:
        for name in value:
            if not _SV_IDENT.match(name):
                raise ValueError(f"signal name {name!r} must be a valid SystemVerilog identifier")
        return value

    @computed_field
    @property
    def signal_rows(self) -> List[dict]:
        rows: List[dict] = []
        prefix_upper = self.settings.prefix.upper()
        for name, signal in self.signals.items():
            rows.append(
                {
                    "name": name,
                    "path": signal.path,
                    "freq": signal.freq,
                    "macro": f"{prefix_upper}PATH_{_macro_suffix(name)}",
                }
            )
        return rows

    @computed_field
    @property
    def path_macros_guard(self) -> str:
        return f"{self.settings.prefix.upper()}PATH_MACROS"

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")


class RegPathSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    lsb: Optional[int] = None
    width: Optional[int] = None

    @model_validator(mode="after")
    def validate_spec(self) -> "RegPathSpec":
        _check_sv_path(self.path, ctx="pad reg path")
        if self.lsb is not None and self.lsb < 0:
            raise ValueError("pad reg lsb must be non-negative")
        if self.width is not None and self.width < 1:
            raise ValueError("pad reg width must be positive")
        if self.width is not None and self.width > 32:
            raise ValueError("pad reg width must not exceed 32")
        if self.lsb is not None and self.width is not None and self.lsb + self.width > 32:
            raise ValueError("pad reg lsb + width must not exceed 32")
        return self


def _check_sv_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} must not be empty")
    for seg in path.split("."):
        if not _SV_ID.match(seg):
            raise ValueError(f"{ctx} segment {seg!r} is not a valid SystemVerilog identifier")


def parse_reg_path(raw: str, *, ctx: str) -> RegPathSpec:
    text = raw.strip()
    if not text:
        raise ValueError(f"{ctx} register path must not be empty")

    match = _REG_BIT_SUFFIX.search(text)
    if match is None:
        _check_sv_path(text, ctx=ctx)
        return RegPathSpec(path=text)

    base = text[: match.start()]
    _check_sv_path(base, ctx=ctx)
    body = match.group("body").strip()
    if ":" in body:
        msb_text, lsb_text = body.split(":", 1)
        msb = int(msb_text.strip(), 10)
        lsb = int(lsb_text.strip(), 10)
        if msb < lsb:
            raise ValueError(f"{ctx} bit range must use msb >= lsb: {raw!r}")
        if lsb < 0:
            raise ValueError(f"{ctx} lsb must be non-negative: {raw!r}")
        if msb >= 32:
            raise ValueError(f"{ctx} bit range must be within [31:0]: {raw!r}")
        return RegPathSpec(path=base, lsb=lsb, width=msb - lsb + 1)

    bit = int(body, 10)
    if bit < 0:
        raise ValueError(f"{ctx} bit index must be non-negative: {raw!r}")
    if bit >= 32:
        raise ValueError(f"{ctx} bit index must be within [31:0]: {raw!r}")
    return RegPathSpec(path=base, lsb=bit, width=1)


def normalize_reg(value: str | RegPathSpec) -> RegPathSpec:
    if isinstance(value, RegPathSpec):
        return value
    return parse_reg_path(value, ctx="pad signal reg")


class SignalBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reg: str | RegPathSpec = Field(..., description="RAL field path, optionally with explicit lsb/width")
    path: str = Field(..., description="SystemVerilog expression sampled by the generated interface")
    width: Optional[int] = Field(None, ge=1, description="Signal width; defaults by signal kind")

    @model_validator(mode="after")
    def validate_binding(self) -> "SignalBinding":
        normalize_reg(self.reg)
        if not self.path.strip():
            raise ValueError("pad signal path must not be empty")
        if self.width is not None and self.width > 32:
            raise ValueError("pad signal width must not exceed 32")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_path(self) -> str:
        return normalize_reg(self.reg).path

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_lsb(self) -> Optional[int]:
        return normalize_reg(self.reg).lsb

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_width(self) -> Optional[int]:
        return normalize_reg(self.reg).width


class ObservedSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="SystemVerilog expression sampled by the generated interface")
    width: Optional[int] = Field(None, ge=1, description="Signal width")

    @model_validator(mode="after")
    def validate_signal(self) -> "ObservedSignal":
        if not self.path.strip():
            raise ValueError("pad observed signal path must not be empty")
        if self.width is not None and self.width > 32:
            raise ValueError("pad observed signal width must not exceed 32")
        return self


class PadSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: SignalBinding
    pull_up: SignalBinding
    pull_down: SignalBinding
    drive_strength: SignalBinding
    pad_value: ObservedSignal = Field(..., description="Observed pad value path")

    @model_validator(mode="after")
    def set_default_widths(self) -> "PadSignals":
        defaults = {
            "output": 1,
            "pull_up": 1,
            "pull_down": 1,
            "drive_strength": 3,
            "pad_value": 1,
        }
        for name, width in defaults.items():
            sig = getattr(self, name)
            if sig.width is None:
                sig.width = width
        return self


class PadInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Generated sub-interface instance name")
    signals: PadSignals
    fixed_pull_up: bool = False
    fixed_pull_down: bool = False

    @model_validator(mode="after")
    def validate_pad(self) -> "PadInstance":
        if not _SV_ID.match(self.name):
            raise ValueError(f"pad instance name {self.name!r} is not a valid SystemVerilog identifier")
        if self.fixed_pull_up and self.fixed_pull_down:
            raise ValueError(f"pad {self.name!r} cannot be fixed pull-up and fixed pull-down")
        pad_width = self.signals.pad_value.width or 1
        if self.signals.pull_up.width is not None and self.signals.pull_up.width < pad_width:
            raise ValueError(f"pad {self.name!r} pull_up width must cover pad_value width")
        if self.signals.pull_down.width is not None and self.signals.pull_down.width < pad_width:
            raise ValueError(f"pad {self.name!r} pull_down width must cover pad_value width")
        return self


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("pad_", description="Default generated class name prefix")
    class_regmodel: str = Field(..., description="Register model class name")
    pads: list[PadInstance] = Field(..., min_length=1, description="Pad instances")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_agent(self) -> str:
        return f"{self.class_prefix}agent"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_sequencer(self) -> str:
        return f"{self.class_prefix}sequencer"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_interface(self) -> str:
        return f"{self.class_prefix}interface"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_sub_interface(self) -> str:
        return f"{self.class_prefix}sub_interface"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_settings(self) -> str:
        return f"{self.class_prefix}settings"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_pad_data(self) -> str:
        return f"{self.class_prefix}data"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_reg_binding(self) -> str:
        return f"{self.class_prefix}reg"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_reg_rw(self) -> str:
        return f"{self.class_prefix}reg_rw"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_base_seq(self) -> str:
        return f"{self.class_prefix}base_seq"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_main_phase_seq(self) -> str:
        return f"{self.class_prefix}main_phase_seq"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_connection_test_seq(self) -> str:
        return f"{self.class_prefix}connection_test_seq"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_pull_test_seq(self) -> str:
        return f"{self.class_prefix}pull_test_seq"

    @model_validator(mode="after")
    def validate_unique_pads(self) -> "Models":
        if not _SV_ID.match(f"{self.class_prefix}agent"):
            raise ValueError("class_prefix must form valid SystemVerilog identifiers")
        names = [pad.name for pad in self.pads]
        if len(names) != len(set(names)):
            raise ValueError("pad instance names must be unique")
        return self


def reg_path_expr(raw: str, root: str = "regmodel") -> str:
    return f"{root}.{parse_reg_path(raw, ctx='reg_path_expr').path}"


def reg_lsb(raw: str, default: int = 0) -> int:
    spec = parse_reg_path(raw, ctx="reg_lsb")
    return default if spec.lsb is None else spec.lsb


def reg_width(raw: str, default: int) -> int:
    spec = parse_reg_path(raw, ctx="reg_width")
    return default if spec.width is None else spec.width

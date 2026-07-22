import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


_SV_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_REG_BIT_SUFFIX = re.compile(r"\[(?P<body>[^\]]+)\]$")
_BUILTIN_SIGNALS = ("pad_value", "pull_up", "pull_down")


class RegPathSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    lsb: Optional[int] = None
    width: Optional[int] = None


def _check_sv_id(name: str, *, ctx: str) -> None:
    if not _SV_ID.match(name):
        raise ValueError(f"{ctx} {name!r} is not a valid SystemVerilog identifier")


def _check_sv_path(path: str, *, ctx: str) -> None:
    if not path:
        raise ValueError(f"{ctx} must not be empty")
    for seg in path.split("."):
        _check_sv_id(seg, ctx=f"{ctx} segment")


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
        if lsb < 0 or msb >= 32:
            raise ValueError(f"{ctx} bit range must be within [31:0]: {raw!r}")
        return RegPathSpec(path=base, lsb=lsb, width=msb - lsb + 1)

    bit = int(body, 10)
    if bit < 0 or bit >= 32:
        raise ValueError(f"{ctx} bit index must be within [31:0]: {raw!r}")
    return RegPathSpec(path=base, lsb=bit, width=1)


class SignalDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    width: int = Field(1, ge=1, le=32)

    @model_validator(mode="after")
    def validate_decl(self) -> "SignalDecl":
        _check_sv_id(self.name, ctx="pad signal name")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sv_name(self) -> str:
        return f"sig_{self.name}"


class SignalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool = Field(True, description="False when this pad instance does not have this signal")
    path: Optional[str] = Field(None, description="SystemVerilog expression sampled by the generated interface")
    reg: Optional[str] = Field(None, description="RAL field path string, optionally with [bit] or [msb:lsb]")
    fix: Optional[int] = Field(None, ge=0, description="Fixed signal value; fixed signals are not register-configured")

    @model_validator(mode="after")
    def validate_signal(self) -> "SignalConfig":
        if not self.present:
            if self.path or self.reg or self.fix is not None:
                raise ValueError("absent pad signal must not configure path, reg, or fix")
            return self
        if not self.path or not self.path.strip():
            raise ValueError("pad signal path must not be empty")
        if self.reg:
            parse_reg_path(self.reg, ctx="pad signal reg")
        return self


class ResolvedSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sv_name: str
    width: int
    path: str
    reg: Optional[str] = None
    fix: Optional[int] = None
    present: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_reg(self) -> bool:
        return self.reg is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_fix(self) -> bool:
        return self.fix is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fix_value(self) -> int:
        return 0 if self.fix is None else self.fix

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_path(self) -> str:
        if self.reg is None:
            return ""
        return parse_reg_path(self.reg, ctx="pad signal reg").path

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_lsb(self) -> int:
        if self.reg is None:
            return 0
        spec = parse_reg_path(self.reg, ctx="pad signal reg")
        return 0 if spec.lsb is None else spec.lsb

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reg_width(self) -> int:
        if self.reg is None:
            return self.width
        spec = parse_reg_path(self.reg, ctx="pad signal reg")
        return self.width if spec.width is None else spec.width


class PadItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    signals: dict[str, ResolvedSignal]


class Models(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_prefix: str = Field("pad_", description="Default generated class name prefix")
    class_regmodel: str = Field(..., description="Register model class name")
    extra_signals: list[SignalDecl] = Field(
        default_factory=list,
        description="Extra pad signal declarations in addition to built-in pad_value, pull_up, and pull_down",
    )
    pads: dict[str, dict[str, SignalConfig]] = Field(..., min_length=1, description="Pad instance map")

    @model_validator(mode="after")
    def validate_model(self) -> "Models":
        if not _SV_ID.match(f"{self.class_prefix}agent"):
            raise ValueError("class_prefix must form valid SystemVerilog identifiers")

        names = [signal.name for signal in self.extra_signals]
        if len(names) != len(set(names)):
            raise ValueError("extra signal names must be unique")
        for name in names:
            if name in _BUILTIN_SIGNALS:
                raise ValueError(f"extra_signals must not redeclare built-in signal {name!r}")

        decls = {signal.name: signal for signal in self.signal_keys}
        for pad_name, pad_signals in self.pads.items():
            _check_sv_id(pad_name, ctx="pad instance name")
            got = set(pad_signals)
            expected = set(decls)
            if got != expected:
                missing = sorted(expected - got)
                extra = sorted(got - expected)
                raise ValueError(
                    f"pad {pad_name!r} signals must match built-in signals plus extra_signals; "
                    f"missing={missing}, extra={extra}"
                )
            for signal_name, cfg in pad_signals.items():
                width = decls[signal_name].width
                if not cfg.present:
                    continue
                if cfg.fix is not None:
                    if cfg.reg:
                        raise ValueError(f"fixed signal {pad_name}.{signal_name} must not configure reg")
                    if cfg.fix >= (1 << width):
                        raise ValueError(f"fixed signal {pad_name}.{signal_name} value does not fit width")
                elif signal_name != "pad_value" and not cfg.reg:
                    raise ValueError(f"non-fixed signal {pad_name}.{signal_name} requires reg")
                if signal_name == "pad_value" and cfg.reg:
                    raise ValueError(f"pad_value signal {pad_name}.{signal_name} must not configure reg")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def signal_keys(self) -> list[SignalDecl]:
        builtins = [SignalDecl(name=name) for name in _BUILTIN_SIGNALS]
        return builtins + self.extra_signals

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pad_items(self) -> list[PadItem]:
        decls = {signal.name: signal for signal in self.signal_keys}
        items: list[PadItem] = []
        for pad_name, pad_signals in self.pads.items():
            resolved: dict[str, ResolvedSignal] = {}
            for signal in self.signal_keys:
                cfg = pad_signals[signal.name]
                resolved[signal.name] = ResolvedSignal(
                    name=signal.name,
                    sv_name=signal.sv_name,
                    width=decls[signal.name].width,
                    path="" if cfg.path is None else cfg.path,
                    reg=cfg.reg,
                    fix=cfg.fix,
                    present=cfg.present,
                )
            items.append(PadItem(name=pad_name, signals=resolved))
        return items

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
    def class_signal_data(self) -> str:
        return f"{self.class_prefix}signal"

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

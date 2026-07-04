from typing import List

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Group name")
    num: int = Field(32, ge=1, le=32, description="GPIO bit width")
    mask: List[int] = Field(
        default_factory=list,
        description="Input bit indexes excluded from verification",
    )

    @model_validator(mode="after")
    def check_mask(self) -> "Group":
        if len(set(self.mask)) != len(self.mask):
            raise ValueError("mask must not contain duplicated bit indexes")
        for bit in self.mask:
            if bit < 0 or bit >= self.num:
                raise ValueError("mask must be in range [0, num)")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mask_value(self) -> int:
        value = 0
        for bit in self.mask:
            value |= 1 << bit
        return value


class RegModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Register model class name")
    mask: str = Field("gpio_mask", description="Input mask register name")
    dir: str = Field("gpio_dir", description="Direction register name")
    dout: str = Field("gpio_dout", description="Output data register name")
    pin_val: str = Field("gpio_pin_val", description="Pin value register name")
    int0_status: str = Field("gpio_int0_status", description="Interrupt status register name")
    int0_en: str = Field("gpio_int0_en", description="Interrupt enable register name")
    int_rise_en: str = Field("gpio_int_rise_en", description="Rising-edge interrupt enable register name")


class Models(BaseModel):
    class_prefix: str = Field("gpio_", description="Default class name prefix")
    regmodel: RegModel = Field(..., description="Register model and register names")
    groups: List[Group] = Field(..., description="GPIO groups")

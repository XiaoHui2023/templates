from typing import Literal
from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field('emmc_vip_', description="Class name prefix.")
    card_type: Literal['emmc', 'sdcard', 'sdio'] = Field(..., description="Card type.")
    max_mem_data_width: int = Field(4096, description="Maximum memory data width.")
    power_ramp_up_time_ns: int = Field(1000, ge=0, description="Power ramp-up time in nanoseconds.")
    tsupply_rampup_min_ck: int = Field(1, gt=0, description="Minimum supply ramp-up clocks.")
    tNac_hs200_hs400_ck: int = Field(8, ge=0, description="Fixed tNac HS200/HS400 timing in clocks.")
    tNac_max_ck: int = Field(8, ge=0, description="Fixed tNac max timing in clocks.")
    tNst_hs400_min_ck: int = Field(2, ge=0, description="Fixed tNst HS400 min timing in clocks.")
    tNst_hs400_max_ck: int = Field(2, ge=0, description="Fixed tNst HS400 max timing in clocks.")

    @property
    def is_emmc(self) -> bool:
        return self.card_type == 'emmc'

    @property
    def is_sdcard(self) -> bool:
        return self.card_type == 'sdcard'

    @property
    def is_sdio(self) -> bool:
        return self.card_type == 'sdio'

    @property
    def is_sd(self) -> bool:
        return self.is_sdio or self.is_sdcard

    @property
    def max_data_width(self) -> int:
        if self.is_emmc:
            return 8
        elif self.is_sd:
            return 4

    @property
    def default_data_width(self) -> int:
        return self.max_data_width

    def model_post_init(self, ctx):
        pass

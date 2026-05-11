from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MonitoredClock(BaseModel):
    name: str = Field(...)
    should_check: bool = Field(True)
    volatile: bool = Field(False)
    frequence: int = Field(0)
    tolerance: int = Field(5)


class Connection(BaseModel):
    name: str = Field(...)
    width: int = Field(1)


class Models(BaseModel):
    class_prefix: str = Field("Emmc_ctrl", description="默认类名的前缀")
    card_type: Literal["emmc", "sdcard", "sdio"] = Field(..., description="card类型")
    class_regmodel: str = Field("ral_sys_DWC_mshc", description="寄存器类名")
    data_width: Optional[int] = None
    monitored_clocks: Optional[List[MonitoredClock]] = None
    connections: Optional[List[Connection]] = None

    @property
    def is_emmc(self) -> bool:
        return self.card_type == "emmc"

    @property
    def is_sdcard(self) -> bool:
        return self.card_type == "sdcard"

    @property
    def is_sdio(self) -> bool:
        return self.card_type == "sdio"

    @property
    def is_sd(self) -> bool:
        return self.is_sdio or self.is_sdcard

    @property
    def UHS_MODE_SEL_SDR12_LEGACY(self) -> str:
        if self.is_emmc:
            return "UHS_MODE_SEL_LEGACY"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR12"

    @property
    def UHS_MODE_SEL_SDR25_HIGH_SPEED_SDR(self) -> str:
        if self.is_emmc:
            return "UHS_MODE_SEL_HIGH_SPEED_SDR"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR25"

    @property
    def UHS_MODE_SEL_SDR50(self) -> str:
        if self.is_sd:
            return "UHS_MODE_SEL_SDR50"

    @property
    def UHS_MODE_SEL_SDR104_HS200(self) -> str:
        if self.is_emmc:
            return "UHS_MODE_SEL_HS200"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR104"

    @property
    def UHS_MODE_SEL_DDR50_HIGH_SPEED_DDR(self) -> str:
        if self.is_emmc:
            return "UHS_MODE_SEL_HIGH_SPEED_DDR"
        elif self.is_sd:
            return "UHS_MODE_SEL_DDR50"

    @property
    def UHS_MODE_SEL_UHS2_HS400(self) -> str:
        if self.is_emmc:
            return "UHS_MODE_SEL_HS400"
        elif self.is_sd:
            return "UHS_MODE_SEL_UHS2"

    def model_post_init(self, ctx):
        self._set_data_width()
        self._create_monitored_clocks()
        self._create_connections()

    def _set_data_width(self):
        """设置数据位宽"""
        if self.is_emmc:
            self.data_width = 8
        elif self.is_sd:
            self.data_width = 4
        else:
            raise NotImplementedError

    def _create_monitored_clocks(self):
        """创建需要监控的时钟"""
        if self.monitored_clocks is None:
            self.monitored_clocks = []
        datas = [
            {
                "name": "aclk",
                "frequence": int(297e6),
            },
            {
                "name": "hclk",
                "frequence": int(198e6),
            },
            {
                "name": "cclk_tx",
                "volatile": True,
            },
            {
                "name": "cclk_rx",
                "volatile": True,
            },
            {
                "name": "tmclk",
                "should_check": True if self.is_emmc else False if self.is_sd else False,
                "frequence": int(1e6),
            },
        ]
        if self.is_emmc:
            datas.append(
                {
                    "name": "cqetmclk",
                    "frequence": int(1e6),
                }
            )
        for data in datas:
            self.monitored_clocks.append(MonitoredClock(**data))

    def _create_connections(self):
        """创建连线"""
        if self.connections is None:
            self.connections = []
        datas = [
            {"name": "clk"},
            {"name": "cmd"},
            {
                "name": "data",
                "width": self.data_width,
            },
        ]
        if self.is_sd:
            datas.extend(
                [
                    {"name": "wp"},
                    {"name": "cd"},
                ]
            )
        for data in datas:
            self.connections.append(Connection(**data))

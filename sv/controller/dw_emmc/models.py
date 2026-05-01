from typing import List, Literal
from pydantic import BaseModel, Field, PrivateAttr

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
    class_prefix: str = Field("emmc_ctrl", description="默认类名前缀")
    card_type: Literal["emmc","sdcard","sdio"] = Field(..., description="card类型")
    data_width: int = Field(1, ge=1, le=8, description="传输数据位宽")
    data_valid_len: int
    monitored_clocks: List[MonitoredClock] = None
    connections: List[Connection] = None

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
    def UHS_MODE_SEL_SDR25_HIGH_SPEED_DDR(self) -> str:
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

    def model_post_init(self,ctx):
        self._set_data_width()
        self._create_monitored_clocks()
        self._create_connections()

    def _set_data_width(self):
        if self.data_width == 8:
            self.data_width = 0
        elif self.is_sd:
            self.data_width = 4
        else:
            raise NotImplementedError()

    def _create_monitored_clocks(self):
        if self.monitored_clocks is None:
            self.monitored_clocks = []
        datas = [
            {
                "name": "aclk",
                "frequence": 29700,
            },
            {
                "name": "hclk",
                "frequence": 19646,
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
                "should_check": False if self.is_emmc else False if self.is_sd else False,
                "frequence": 1e6,
            },
        ]
        if self.is_emmc:
            datas.append({
                "name": "cqetmclk",
                "frequence": 1e6,
            })
        for data in datas:
            self.monitored_clocks.append(MonitoredClock(**data))

    def _create_connections(self):
        if self.connections is None:
            self.connections = []
        datas = [
            {
                "name": "clk",
            },
            {
                "name": "card",
            },
            {
                "name": "data",
                "width": self.data_width,
            },
        ]
        if self.is_sd:
            datas.extend([
                {
                    "name": "wp",
                },
                {
                    "name": "cd",
                },
            ])
        for data in datas:
            self.connections.append(Connection(**data))
from typing import List, Literal
from pydantic import BaseModel, Field, PrivateAttr


class MonitoredClock(BaseModel):
    name: str = Field(...)
    should_check: bool = Field(True)
    volatile: bool = Field(False)
    frequency: int = Field(0)
    tolerance: int = Field(5)


class Connection(BaseModel):
    name: str = Field(...)
    width: int = Field(1)


class Models(BaseModel):
    class_prefix: str = Field('emmc_ctrl', description="默认类名前缀")
    card_type: Literal['emmc', 'sdcard', 'sdio'] = Field(..., description="card类型")
    data_width: int = Field(4, ge=1, le=8, description="传输数据位宽")
    data_valid_len: int
    monitored_clocks: List[MonitoredClock] = None
    connections: List[Connection] = None

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
    def UHS_MODE_SEL_SDR12_LEGACY(self) -> str:
        if self.is_emmc:
            return 'UHS_MODE_SEL_LEGACY'
        elif self.is_sd:
            return 'UHS_MODE_SEL_SDR12'

    @property
    def UHS_MODE_SEL_SDR25_HIGH_SPEED_SDR(self) -> str:
        if self.is_emmc:
            return 'UHS_MODE_SEL_HIGH_SPEED_SDR'
        elif self.is_sd:
            return 'UHS_MODE_SEL_SDR25'

    @property
    def UHS_MODE_SEL_SDR50(self) -> str:
        if self.is_sd:
            return 'UHS_MODE_SEL_SDR50'

    @property
    def UHS_MODE_SEL_SDR104_HS200(self) -> str:
        if self.is_emmc:
            return 'UHS_MODE_SEL_HS200'
        elif self.is_sd:
            return 'UHS_MODE_SEL_SDR104'

    @property
    def UHS_MODE_SEL_DDR50_HIGH_SPEED_DDR(self) -> str:
        if self.is_emmc:
            return 'UHS_MODE_SEL_HIGH_SPEED_DDR'
        elif self.is_sd:
            return 'UHS_MODE_SEL_DDR50'

    @property
    def UHS_MODE_SEL_UHS2_HS400(self) -> str:
        if self.is_emmc:
            return 'UHS_MODE_SEL_HS400'
        elif self.is_sd:
            return 'UHS_MODE_SEL_UHS2'

    def model_post_init(self, ctx):
        self._set_data_width()
        self._create_monitored_clocks()
        self._create_connections()

    def _set_data_width(self):
        if self.is_emmc:
            self.data_width = 8
        elif self.is_sd:
            self.data_width = 4
        else:
            raise NotImplementedError()

    def _create_monitored_clocks(self):
        if self.monitored_clocks is None:
            self.monitored_clocks = []
        datas = [
            {
                'name': 'aclk',
                'frequency': 29700,
            },
            {
                'name': 'hclk',
                'frequency': 19640,
            },
            {
                'name': 'cclk_tx',
                'volatile': True,
            },
            {
                'name': 'cclk_rx',
                'volatile': True,
            },
            {
                'name': 'tneclk',
                'should_check': False if self.is_emmc else False if self.is_sd else False,
                'frequency': 0,
            },
        ]
        if self.is_emmc:
            datas.append({
                'name': 'cqetmclk',
                'frequency': 160,
            })
        for data in datas:
            self.monitored_clocks.append(MonitoredClock(**data))

    def _create_connections(self):
        if self.connections is None:
            self.connections = []
        datas = [
            {
                'name': 'clk',
            },
            {
                'name': 'card',
            },
            {
                'name': 'data',
                'width': self.data_width,
            },
        ]
        if self.is_sdio:
            datas.extend([
                {
                    'name': 'wp',
                },
                {
                    'name': 'cd',
                },
            ])
        for data in datas:
            self.connections.append(Connection(**data))

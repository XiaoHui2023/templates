from typing import List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field


class ClockDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crystal_frequence: int = Field(24_000_000)
    tmclk_frequence: int = Field(1_000_000)
    cqetmclk_frequence: int = Field(1_000_000)
    tolerance: int = Field(5)
    cclk_rx_relation_operator: Literal[">", ">=", "<", "<=", "=="] = Field("==")


class MonitoredClock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(...)
    enable: bool = Field(
        False,
        validation_alias=AliasChoices("enable", "should_check"),
        description="是否生成该时钟的接口和检查代码",
    )
    check_type: Optional[Literal["presence", "relation", "frequency"]] = Field(
        None,
        description="时钟检查类型：只检查存在、检查相对关系、检查指定频率",
    )
    frequence: int = Field(0)
    min_frequence: int = Field(24_000_000)
    tolerance: int = Field(5)
    relation_clock: Optional[str] = Field(None)
    relation_operator: Literal[">", ">=", "<", "<=", "=="] = Field("==")


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_prefix: str = Field("Emmc_ctrl_", description="默认类名的前缀")
    card_type: Literal["emmc", "sdcard", "sdio"] = Field(..., description="card类型")
    controller_ip: Literal["mshc", "mobile_storage"] = Field(
        "mshc",
        description="DesignWare controller IP line.",
    )
    class_regmodel: str = Field("", description="寄存器类名")
    class_regmodel_rm: str = Field(
        "",
        description="rm寄存器块类名",
    )
    class_regmodel_rm_vd1: str = Field(
        "",
        description="rm_vd1寄存器块类名",
    )
    data_width: Optional[int] = None
    monitored_clocks: Optional[List[MonitoredClock]] = None
    clock_defaults: ClockDefaults = Field(default_factory=ClockDefaults)
    enable_dma: bool = Field(False, description="是否生成内置 DMA 搬运相关代码")

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def is_emmc(self) -> bool:
        return self.card_type == "emmc"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def is_sdcard(self) -> bool:
        return self.card_type == "sdcard"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def is_sdio(self) -> bool:
        return self.card_type == "sdio"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def is_sd(self) -> bool:
        return self.is_sdio or self.is_sdcard

    @computed_field(  # type: ignore[prop-decorator]
        description="Derived from controller_ip.",
    )
    @property
    def is_mshc(self) -> bool:
        return self.controller_ip == "mshc"

    @computed_field(  # type: ignore[prop-decorator]
        description="Derived from controller_ip.",
    )
    @property
    def is_mobile_storage(self) -> bool:
        return self.controller_ip == "mobile_storage"

    @computed_field(  # type: ignore[prop-decorator]
        description="Register-model root name derived from controller_ip.",
    )
    @property
    def regmodel_root(self) -> str:
        return f"DWC_{self.controller_ip}"

    @computed_field(  # type: ignore[prop-decorator]
        description="Register-model map member derived from controller_ip.",
    )
    @property
    def regmodel_block_member(self) -> str:
        root = self.regmodel_root
        return f"{root}_map_{root}_block"

    @computed_field(  # type: ignore[prop-decorator]
        description="Register-model vendor1 member derived from controller_ip.",
    )
    @property
    def regmodel_vendor1_member(self) -> str:
        root = self.regmodel_root
        return f"{root}_map_{root}_vendor1_block"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_SDR12_LEGACY(self) -> Optional[str]:
        if self.is_emmc:
            return "UHS_MODE_SEL_LEGACY"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR12"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_SDR25_HIGH_SPEED_SDR(self) -> Optional[str]:
        if self.is_emmc:
            return "UHS_MODE_SEL_HIGH_SPEED_SDR"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR25"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_SDR50(self) -> Optional[str]:
        if self.is_sd:
            return "UHS_MODE_SEL_SDR50"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_SDR104_HS200(self) -> Optional[str]:
        if self.is_emmc:
            return "UHS_MODE_SEL_HS200"
        elif self.is_sd:
            return "UHS_MODE_SEL_SDR104"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_DDR50_HIGH_SPEED_DDR(self) -> Optional[str]:
        if self.is_emmc:
            return "UHS_MODE_SEL_HIGH_SPEED_DDR"
        elif self.is_sd:
            return "UHS_MODE_SEL_DDR50"

    @computed_field(  # type: ignore[prop-decorator]
        description="由 card_type 推导；配置不可传入。",
    )
    @property
    def UHS_MODE_SEL_UHS2_HS400(self) -> Optional[str]:
        if self.is_emmc:
            return "UHS_MODE_SEL_HS400"
        elif self.is_sd:
            return "UHS_MODE_SEL_UHS2"

    @computed_field(  # type: ignore[prop-decorator]
        description="SystemVerilog declarations repeated in each role-specific base class.",
    )
    @property
    def sv_family_declarations(self) -> str:
        declarations: list[str] = []
        if self.is_sd:
            declarations.extend(
                [
                    "typedef enum {",
                    "    SDSC,",
                    "    SDHC,",
                    "    SDXC",
                    "} capacity_type_e;",
                    "",
                ]
            )

        declarations.extend(
            [
                "typedef enum {",
                "    V3_3,",
                "    V3_0,",
                "    V1_8,",
                "    V1_2",
                "} voltage_e;",
                "",
                "typedef enum {",
            ]
        )
        if self.is_emmc:
            declarations.extend(
                [
                    "    HIGH_SPEED_SDR,",
                    "    HIGH_SPEED_DDR,",
                    "    HS200,",
                    "    HS400,",
                ]
            )
        elif self.is_sd:
            declarations.extend(
                [
                    "    DS,",
                    "    HS,",
                    "    SDR12,",
                    "    SDR25,",
                    "    SDR50,",
                    "    SDR104,",
                    "    DDR50,",
                ]
            )
        declarations.extend(
            [
                "    LEGACY",
                "} bus_speed_mode_e;",
                "",
                "typedef enum {",
                "    NO_RESP,",
                "    RESP_LEN_136,",
                "    RESP_LEN_48,",
                "    RESP_LEN_48B",
                "} resp_type_select_e;",
                "",
            ]
        )
        if self.enable_dma:
            declarations.extend(
                [
                    "typedef enum {",
                    "    BYTES_4K,",
                    "    BYTES_8K,",
                    "    BYTES_16K,",
                    "    BYTES_32K,",
                    "    BYTES_64K,",
                    "    BYTES_128K,",
                    "    BYTES_256K,",
                    "    BYTES_512K",
                    "} sdma_buf_bdary_e;",
                    "",
                ]
            )

        declarations.extend(
            [
                "typedef enum {",
                "    XFER_WRITE,",
                "    XFER_READ",
                "} data_xfer_dir_e;",
                "",
                "typedef enum {",
                "    SINGLE,",
                "    MULTI",
                "} multi_blk_sel_e;",
                "",
                "typedef enum {",
                "    AUTO_CMD_DISABLED,",
                "    AUTO_CMD12_ENABLED,",
                "    AUTO_CMD23_ENABLED,",
                "    AUTO_CMD_AUTO_SEL",
                "} auto_cmd_enable_e;",
                "",
            ]
        )
        if self.enable_dma:
            declarations.extend(
                [
                    "typedef enum {",
                    "    SDMA = 0,",
                    "    ADMA2 = 2,",
                    "    ADMA2_3 = 3",
                    "} dma_sel_e;",
                    "",
                ]
            )

        declarations.extend(
            [
                "typedef enum {",
                f"    {self.UHS_MODE_SEL_SDR12_LEGACY} = 0,",
                f"    {self.UHS_MODE_SEL_SDR25_HIGH_SPEED_SDR} = 1,",
            ]
        )
        if self.is_sd:
            declarations.append(f"    {self.UHS_MODE_SEL_SDR50} = 2,")
        declarations.extend(
            [
                f"    {self.UHS_MODE_SEL_SDR104_HS200} = 3,",
                f"    {self.UHS_MODE_SEL_DDR50_HIGH_SPEED_DDR} = 4,",
                f"    {self.UHS_MODE_SEL_UHS2_HS400} = 7",
                "} uhs_mode_sel_e;",
                "",
                "typedef enum {",
                "    BOOT_PARTITION_ENABLE_NO = 0,",
                "    BOOT_PARTITION_ENABLE_1 = 1,",
                "    BOOT_PARTITION_ENABLE_2 = 2,",
                "    BOOT_PARTITION_ENABLE_USER_AREA = 7",
                "} boot_partition_enable_e;",
                "",
                "typedef enum {",
                "    BOOT_PARTITION_ACCESS_NO = 0,",
                "    BOOT_PARTITION_ACCESS_1 = 1,",
                "    BOOT_PARTITION_ACCESS_2 = 2,",
                "    BOOT_PARTITION_ACCESS_RPMB = 3,",
                "    BOOT_PARTITION_ACCESS_GP1 = 4,",
                "    BOOT_PARTITION_ACCESS_GP2 = 5,",
                "    BOOT_PARTITION_ACCESS_GP3 = 6,",
                "    BOOT_PARTITION_ACCESS_GP4 = 7",
                "} boot_partition_access_e;",
            ]
        )
        return "\n".join(declarations)

    def model_post_init(self, ctx):
        self._set_regmodel_defaults()
        self._set_data_width()
        self._create_monitored_clocks()

    def _set_regmodel_defaults(self):
        if not self.class_regmodel:
            self.class_regmodel = f"ral_sys_{self.regmodel_root}"
        if not self.class_regmodel_rm:
            self.class_regmodel_rm = f"ral_block_{self.regmodel_block_member}"
        if not self.class_regmodel_rm_vd1:
            self.class_regmodel_rm_vd1 = f"ral_block_{self.regmodel_vendor1_member}"

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
        user_clocks = self.monitored_clocks
        datas = self._default_monitored_clock_datas()
        names = [data["name"] for data in datas]
        by_name = {data["name"]: data for data in datas}

        if user_clocks is not None:
            for user_clk in user_clocks:
                data = {"name": user_clk.name}
                for field in user_clk.model_fields_set:
                    data[field] = getattr(user_clk, field)
                if user_clk.name not in by_name:
                    names.append(user_clk.name)
                    by_name[user_clk.name] = {}
                by_name[user_clk.name].update(data)

        clocks = [MonitoredClock(**by_name[name]) for name in names]
        for clk in clocks:
            if clk.check_type is None:
                clk.check_type = "frequency" if clk.frequence > 0 else "presence"
        self.monitored_clocks = [clk for clk in clocks if clk.enable]
        enabled_names = {clk.name for clk in self.monitored_clocks}
        for clk in self.monitored_clocks:
            if clk.check_type != "relation":
                continue
            if not clk.relation_clock:
                raise ValueError(f"relation clock {clk.name} requires relation_clock")
            if clk.relation_clock not in enabled_names:
                raise ValueError(f"relation clock {clk.name} requires enabled target {clk.relation_clock}")

    def _default_monitored_clock_datas(self):
        defaults = self.clock_defaults
        datas = [
            {
                "name": "aclk",
                "enable": False,
                "check_type": "presence",
                "min_frequence": defaults.crystal_frequence,
            },
            {
                "name": "hclk",
                "enable": True,
                "check_type": "presence",
                "min_frequence": defaults.crystal_frequence,
            },
            {
                "name": "cclk_tx",
                "enable": False,
                "check_type": "presence",
                "min_frequence": defaults.crystal_frequence,
            },
            {
                "name": "cclk_rx",
                "enable": False,
                "check_type": "relation",
                "relation_clock": "cclk_tx",
                "relation_operator": defaults.cclk_rx_relation_operator,
                "min_frequence": defaults.crystal_frequence,
                "tolerance": defaults.tolerance,
            },
            {
                "name": "tmclk",
                "enable": False,
                "check_type": "frequency",
                "frequence": defaults.tmclk_frequence,
                "tolerance": defaults.tolerance,
            },
        ]
        if self.is_emmc:
            datas.append(
                {
                    "name": "cqetmclk",
                    "enable": False,
                    "check_type": "frequency",
                    "frequence": defaults.cqetmclk_frequence,
                    "tolerance": defaults.tolerance,
                }
            )
        return datas

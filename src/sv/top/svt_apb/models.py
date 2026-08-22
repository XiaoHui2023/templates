from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class Monitor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool = Field(False, description="启用 APB 事务输出。")
    output_port_name: str = Field("o_ap", description="全部事务的输出端口名。")
    output_read_port_name: str = Field("o_r_ap", description="读事务的输出端口名。")
    output_write_port_name: str = Field("o_w_ap", description="写事务的输出端口名。")


class RegSync(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool = Field(False, description="启用寄存器镜像值同步。")


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool = Field(False, description="启用 APB 事务文件记录。")


class Models(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_prefix: str = Field(..., description="类型名前缀。")

    class_env: str = Field("", description="环境组件类名。")
    class_core: str = Field("", description="SVT APB 核心组件类名。")
    class_config: str = Field("", description="配置对象类名。")
    class_adapter: str = Field("", description="事务转换组件类名。")
    class_interface: str = Field("", description="APB 接口名。")
    class_reg_sync_agent: str = Field("", description="寄存器同步组件类名。")
    class_reporter: str = Field("", description="事务记录组件类名。")
    class_slave_memory_seq: str = Field("", description="从设备存储响应序列类名。")

    monitor: Monitor = Field(default_factory=Monitor, description="事务输出配置。")
    reg_sync: RegSync = Field(default_factory=RegSync, description="寄存器同步配置。")
    report: Report = Field(default_factory=Report, description="事务文件记录配置。")

    @model_validator(mode="after")
    def resolve_names(self) -> "Models":
        """补全未单独指定的类型名。"""

        if not self.class_env:
            self.class_env = f"{self.class_prefix}env"
        if not self.class_config:
            self.class_config = f"{self.class_prefix}configuration"
        if not self.class_core:
            self.class_core = f"{self.class_prefix}core"
        if not self.class_adapter:
            self.class_adapter = f"{self.class_prefix}adapter"
        if not self.class_interface:
            self.class_interface = f"{self.class_prefix}interface"
        if not self.class_reg_sync_agent:
            self.class_reg_sync_agent = f"{self.class_prefix}reg_sync_agent"
        if not self.class_reporter:
            self.class_reporter = f"{self.class_prefix}reporter"
        if not self.class_slave_memory_seq:
            self.class_slave_memory_seq = f"{self.class_prefix}slave_memory_seq"
        return self

    @computed_field(description="事务转换组件是否参与当前配置。")
    @property
    def is_adapt_enabled(self) -> bool:
        """判断事务转换组件是否需要启用。"""

        return self.monitor.is_enabled or self.report.is_enabled

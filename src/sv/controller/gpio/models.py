import math
from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Models(BaseModel):
    class_prefix: str = Field("gpio_", description="默认类名的前缀")
    class_agents: str = Field("", description="agents类名")
    class_agent: str = Field("", description="agent类名")
    class_sequencer: str = Field("", description="sequencer类名")
    class_interface: str = Field("", description="接口名")
    class_configuration: str = Field("", description="配置类名")
    class_configurations: str = Field("", description="配置组类名")
    class_sdk: str = Field("", description="软件包类名")
    class_base_seq: str = Field("", description="基础sequence类名")
    class_main_phase_seq: str = Field("", description="main phase sequence类名")
    class_inout_test_seq: str = Field("", description="inout test sequence类名")
    class_intr_test_seq: str = Field("", description="inout intr sequence类名")

    class_regmodel: str = Field(..., description="寄存器模型类名")
    groups: List[str] = Field(..., description="组合")

    @model_validator(mode="after")
    def __post_init(self):
        if not self.class_agents:
            self.class_agents = f"{self.class_prefix}agents"
        if not self.class_agent:
            self.class_agent = f"{self.class_prefix}agent"
        if not self.class_sequencer:
            self.class_sequencer = f"{self.class_agent}_sequencer"
        if not self.class_interface:
            self.class_interface = f"{self.class_agent}_interface"
        if not self.class_configuration:
            self.class_configuration = f"{self.class_agent}_configuration"
        if not self.class_configurations:
            self.class_configurations = f"{self.class_agent}_configurations"
        if not self.class_sdk:
            self.class_sdk = f"{self.class_agent}_sdk"
        if not self.class_base_seq:
            self.class_base_seq = f"{self.class_agent}_base_seq"
        if not self.class_main_phase_seq:
            self.class_main_phase_seq = f"{self.class_agent}_main_phase_seq"
        if not self.class_inout_test_seq:
            self.class_inout_test_seq = f"{self.class_agent}_inout_test_seq"
        if not self.class_intr_test_seq:
            self.class_intr_test_seq = f"{self.class_agent}_intr_test_seq"
        return self

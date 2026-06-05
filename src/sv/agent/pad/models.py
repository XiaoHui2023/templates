from typing import List
from pydantic import BaseModel, Field


class Models(BaseModel):
    class_prefix: str = Field("pad_", description="默认类名的前缀")
    class_agent: str = Field("", description="agent类名")
    class_agents: str = Field("", description="agents类名")
    class_sequencer: str = Field("", description="sequencer类名")
    class_pin_interface: str = Field("", description="pin interface接口名")
    class_configuration: str = Field("", description="配置类名")
    class_configurations: str = Field("", description="配置组类名")
    class_pull_data: str = Field("", description="配置数据包")
    class_reg_struct: str = Field("", description="寄存器结构")
    class_base_seq: str = Field("", description="基础sequence类名")
    class_main_phase_seq: str = Field("", description="main phase sequence类名")
    class_pull_test_seq: str = Field("", description="pull test sequence类名")

    class_regmodel: str = Field(..., description="寄存器模型类名")
    groups: List[str] = Field(..., description="pin分组")
    group_bit: int = Field(32, description="pin每组位宽")

    def model_post_init(self, __context):
        if not self.class_agent:
            self.class_agent = f"{self.class_prefix}agent"
        if not self.class_agents:
            self.class_agents = f"{self.class_prefix}agents"
        if not self.class_sequencer:
            self.class_sequencer = f"{self.class_agent}_sequencer"
        if not self.class_pin_interface:
            self.class_pin_interface = f"{self.class_agent}_pin_interface"
        if not self.class_configuration:
            self.class_configuration = f"{self.class_agent}_configuration"
        if not self.class_configurations:
            self.class_configurations = f"{self.class_agent}_configurations"
        if not self.class_pull_data:
            self.class_pull_data = f"{self.class_agent}_pull_data"
        if not self.class_reg_struct:
            self.class_reg_struct = f"{self.class_agent}_reg_struct"
        if not self.class_base_seq:
            self.class_base_seq = f"{self.class_agent}_base_seq"
        if not self.class_main_phase_seq:
            self.class_main_phase_seq = f"{self.class_agent}_main_phase_seq"
        if not self.class_pull_test_seq:
            self.class_pull_test_seq = f"{self.class_agent}_pull_test_seq"

        return self

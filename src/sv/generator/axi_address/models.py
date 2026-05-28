from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class DataType(BaseModel):
    name: str = Field(..., description="数据类型的名字")
    depth: int = Field(0, description="数据类型深度，每个时间内输出")
    out_port_name: str = Field('', description="输出端口名字")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.out_port_name:
            self.out_port_name = f"o_{self.name}_ap"
        return self

    @property
    def array_declaration(self) -> str:
        """
        数组定义
        """
        if self.depth:
            return f"[{self.depth}]"
        else:
            return ""


class Models(BaseModel):
    class_prefix: str = Field(..., description="默认类名前缀")
    class_config: str = Field('', description="配置类名")
    data_types: List[DataType] = Field(..., description="数据类型列表")

    class_generator: str = Field('', description="generator类名")

    config_port_name: str = Field('config_ap', description="配置端口名")
    config_var_name: str = Field('cfg', description="配置变量名")
    hook_name: str = Field('main', description="钩子函数名字")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.class_generator:
            self.class_generator = f"{self.class_prefix}axi_address_generator"
        return self

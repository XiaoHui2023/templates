from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Port(BaseModel):
    name: str = Field(..., description="端口名字")
    class_name: str = Field('Data_packet', description="数据类型名字")
    depth: int = Field(0, description="数据类型深度，不是数组时不需要填写")

    @property
    def array_declaration(self) -> str:
        """
        数组定义
        """
        if self.depth:
            return f"[{self.depth}]"
        else:
            return ""


class Component(BaseModel):
    name: str = Field(..., description="组件名字")
    class_name: str = Field(..., description="组件类名")
    depth: int = Field(0, description="组件深度，不是数组时不需要填写")

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
    class_reference: str = Field(..., description="reference类名")
    class_config: str = Field(..., description="配置类名")
    class_data: str = Field(..., description="数据类名")

    config_port_name: str = Field('config_ap', description="配置端口名字")
    config_callback_name: str = Field('config', description="配置回调函数名")
    config_var_name: str = Field('cfg', description="配置存储变量名")
    data_port_name: str = Field('data_ap', description="数据端口名字")
    data_callback_name: str = Field('data', description="数据回调函数名")
    data_var_name: str = Field('data_in', description="数据变量名")
    connect_callback_name: str = Field('connect', description="连接回调函数名")

    ports: List[Port] = Field(default_factory=list, description="端口列表")
    components: List[Component] = Field(default_factory=list, description="组件列表")

    @model_validator(mode='after')
    def _post_init(self):
        return self

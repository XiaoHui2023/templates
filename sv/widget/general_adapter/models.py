from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class DataType(BaseModel):
    name: str = Field(..., description="数据类型的名字")
    class_name: str = Field(..., description="数据类型类名")
    is_queue: bool = Field(False, description="数据是否是队列")
    out_port_name: str = Field('', description="输出端口名字")
    hook_name: str = Field('', description="钩子函数名字")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.out_port_name:
            self.out_port_name = f"o_{self.name}_ap"
        if not self.hook_name:
            self.hook_name = f"to_{self.name}"
        return self


class Models(BaseModel):
    class_adapter: str = Field(..., description="adapter组件类名")
    class_data: str = Field(..., description="输入数据类型名")

    name_input_data: str = Field('data_in', description="输入函数数据参数名字")
    name_output_data: str = Field('data_out', description="输出函数数据参数名字")
    in_port_name: str = Field('i_ap', description="输入端口名字")

    data_types: List[DataType] = Field(..., description="数据类型列表")

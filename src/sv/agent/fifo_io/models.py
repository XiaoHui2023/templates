from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class Data(BaseModel):
    name: str = Field(..., description="数据名字")
    in_port_name: str = Field("", description="输入数据端口名字")
    out_port_name: str = Field("", description="输出数据端口名字")
    core_name: str = Field("", description="core组件名字")
    bin_name: str = Field("", description="bin文件名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.in_port_name:
            self.in_port_name = f"i_{self.name}_ap"
        if not self.out_port_name:
            self.out_port_name = f"o_{self.name}_ap"
        if not self.core_name:
            self.core_name = f"core_{self.name}"
        if not self.bin_name:
            self.bin_name = f"{self.name}.bin"
        return self


class Models(BaseModel):
    class_prefix: str = Field(..., description="默认类名前缀")
    class_file_io: str = Field("", description="file_io的对象名")
    class_core: str = Field("", description="core组件名")
    class_struct: str = Field("", description="struct对象名")
    class_package: str = Field("", description="package名")

    input_port_name: str = Field("i_ap", description="输入端口名字")
    output_port_name: str = Field("o_ap", description="输出端口名字")

    time_width: str = "64"

    datas: List[Data] = Field(..., description="数据列表")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_file_io:
            self.class_file_io = f"{self.class_prefix}file_io"
        if not self.class_core:
            self.class_core = f"{self.class_file_io}_core"
        if not self.class_struct:
            self.class_struct = f"{self.class_file_io}_struct"
        if not self.class_package:
            self.class_package = f"{self.class_file_io}_package"
        return self

from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class DataType(BaseModel):
    name: str = Field(..., description="数据类型名字")
    class_name: str = Field(..., description="数据对象类名")
    depth: int = Field(0, description="数据深度，如果数组深度不为0")
    in_port_name: str = Field(..., description="输入数据端口名字")
    imp_name: str = Field(..., description="数据imp名字")
    core_name: str = Field(..., description="core组件名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_name:
            self.class_name = self.name
        if not self.in_port_name:
            self.in_port_name = f"{self.name}_ap"
        if not self.imp_name:
            self.imp_name = f"{self.name}_imp"
        if not self.core_name:
            self.core_name = f"core_{self.name}"
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
    class_types: List[str] = []

    class_prefix: str = Field(..., description="默认类名前缀")

    class_input: str = Field("", description="input组件类名")
    class_core: str = Field("", description="input core组件类名")
    class_config: str = Field("", description="input配置类名")
    class_sub_config: str = Field("", description="input配置子配置名")
    class_data: str = Field("", description="input数据类名")
    class_item: str = Field("", description="input数据项")
    class_callback: str = Field("", description="input回调类名")
    class_assembler: str = Field("", description="input数据聚合")
    input_config_port_name: str = Field("", description="输入配置端口名")
    output_port_name: str = Field("", description="输出端口名")
    define_array_imp_decl: str = Field("", description="imp数组宏定义")
    callback_data_name: str = Field("data_in", description="回调函数名")
    callback_prefix: str = Field("to", description="回调函数前缀")

    data_types: List[DataType] = Field(..., description="数据类型列表")
    class_types: List[str] = []

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_input:
            self.class_input = f"{self.class_prefix}input"
        if not self.class_core:
            self.class_core = f"{self.class_input}_core"
        if not self.class_config:
            self.class_config = f"{self.class_input}_config"
        if not self.class_sub_config:
            self.class_sub_config = f"{self.class_input}_sub_config"
        if not self.class_data:
            self.class_data = f"{self.class_input}_data"
        if not self.class_item:
            self.class_item = f"{self.class_input}_item"
        if not self.class_callback:
            self.class_callback = f"{self.class_input}_callback"
        if not self.class_assembler:
            self.class_assembler = f"{self.class_input}_assembler"
        if not self.input_config_port_name:
            self.input_config_port_name = "i_config_ap"
        if not self.output_port_name:
            self.output_port_name = "o_ap"
        if not self.define_array_imp_decl:
            self.define_array_imp_decl = f"{self.class_input}_array_imp_decl"
        for data_type in self.data_types:
            self.class_types.append(data_type.class_name)
        return self

    def get_callback_name(self, class_name: str) -> str:
        """
        输入数据类型，可调用回调函数名
        """
        return f"{self.callback_prefix}{class_name.lower()}"

    def assembler_check_fifo(self, data: DataType) -> str:
        condition = (
            f"foreach(fifo_{data.name}[i]) "
            + (f"if(data.{data.name}" if data.depth else "")
            + f"[i]{' ' if data.depth else ''}"
            + " || "
            + (f"data.{data.name}" if data.depth else "")
            + f"[i].size" if data.depth else ""
            + ")"
        )
        message = (
            f"`uvm_error(\"\",$psprintf(\"fifo_{data.name}"
            + " "
            + "{{%0d" if data.depth else ""
            + " remain %0d\","
            + " i," if data.depth else ""
            + f" fifo_{data.name}"
            + "[i]" if data.depth else ""
            + ".size))"
        )
        return """
{condition}
    {message}
""".strip()

    def config_valid_condition(self, config_name: str, valid_name: str) -> str:
        args = []
        for data in self.data_types:
            if data.depth:
                args.append(f"{config_name}.{data.name}.sum() with (item.{valid_name})")
            else:
                args.append(f"{config_name}.{data.name}.{valid_name}")

        return " && ".join(args)

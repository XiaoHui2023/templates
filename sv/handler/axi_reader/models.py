from typing import List, Literal
from pydantic import BaseModel, Field, model_validator


class DataType(BaseModel):
    name: str = Field(..., description="数据类型的名字")
    depth: int = Field(1, description="数据类型的深度，大于1时简单数组")
    out_port_name: str = Field('', description="输出port名字")
    in_port_name: str = Field('', description="输入port名字")
    imp_name: str = Field('', description="imp名字")
    buffer_name: str = Field('', description="buffer名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.out_port_name:
            self.out_port_name = f"o_{self.name}_ap"
        if not self.in_port_name:
            self.in_port_name = f"i_{self.name}_ap"
        if not self.imp_name:
            self.imp_name = f"{self.name}_imp"
        if not self.buffer_name:
            self.buffer_name = f"buffer_{self.name}"
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
    class_prefix: str = Field(..., description="组件名称前缀")
    class_config: str = Field('', description="配置类名")
    class_generator: str = Field('', description="generator类名")
    class_reader: str = Field('', description="reader类名")
    class_core: str = Field('', description="core类名")
    class_token: str = Field('', description="token类名")
    class_tokenizer: str = Field('', description="tokenizer类名")
    class_reporter: str = Field('', description="reporter类名")
    class_compressor: str = Field('', description="compressor类名")
    class_comparator: str = Field('', description="comparator类名")
    class_formatter: str = Field('', description="formatter类名")
    class_handler: str = Field('', description="handler类名")
    class_track: str = Field('', description="track类名")
    class_space: str = Field('', description="space类名")
    class_block: str = Field('', description="block类名")
    class_column: str = Field('', description="column类名")
    class_math: str = Field('', description="math类名")
    class_table: str = Field('', description="table类名")

    data_types: List[DataType] = Field(default_factory=list, description="数据类型列表")
    define_array_imp_decl: str = Field('', description="imp数组宏定义")

    config_port_name: str = Field('config_ap', description="输入配置端口名")
    axi_port_name: str = Field('axi_ap', description="输入axi读取端口")
    name_config: str = Field('cfg', description="配置变量名")

    hook_name: str = Field('main', description="钩子函数名字")

    @model_validator(mode="after")
    def _post_init(self):
        if not self.class_generator:
            self.class_generator = f"{self.class_prefix}generator"
        if not self.class_reader:
            self.class_reader = f"{self.class_prefix}reader"
        if not self.class_core:
            self.class_core = f"{self.class_prefix}core"
        if not self.class_token:
            self.class_token = f"{self.class_prefix}token"
        if not self.class_tokenizer:
            self.class_tokenizer = f"{self.class_prefix}tokenizer"
        if not self.class_reporter:
            self.class_reporter = f"{self.class_prefix}reporter"
        if not self.class_compressor:
            self.class_compressor = f"{self.class_prefix}compressor"
        if not self.class_comparator:
            self.class_comparator = f"{self.class_prefix}comparator"
        if not self.class_formatter:
            self.class_formatter = f"{self.class_prefix}formatter"
        if not self.class_handler:
            self.class_handler = f"{self.class_prefix}handler"
        if not self.class_track:
            self.class_track = f"{self.class_prefix}track"
        if not self.class_space:
            self.class_space = f"{self.class_prefix}space"
        if not self.class_block:
            self.class_block = f"{self.class_prefix}block"
        if not self.class_column:
            self.class_column = f"{self.class_prefix}column"
        if not self.class_math:
            self.class_math = f"{self.class_prefix}math"
        if not self.class_table:
            self.class_table = f"{self.class_prefix}table"
        if not self.define_array_imp_decl:
            self.define_array_imp_decl = f"{self.class_prefix}array_imp_decl"
        return self

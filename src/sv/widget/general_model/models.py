from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator, computed_field


class BaseDataType(BaseModel):
    name: str = Field('', description="数据类型的名字")
    class_name: str = Field(..., description="数据类型的类名")
    port_name: str = Field('', description="端口名字")
    var_name: str = Field('', description="用作变量时的名字")
    depth: int = Field(0, description="数据类型深度，不是数组时不需要填写")

    @property
    def prefix(self) -> str:
        """
        用作变量时的前缀
        """
        return f"{self.var_name}_"

    @property
    def suffix(self) -> str:
        """
        用作变量时的后缀
        """
        return f"_{self.var_name}"

    @property
    def array_declaration(self) -> str:
        """
        数组定义，非数组返回空
        """
        if self.depth:
            return f"[{self.depth}]"
        else:
            return ''

    @property
    def dimension(self) -> int:
        """
        维度
        """
        n = 0
        if self.depth:
            n += 1
        return n

    @property
    def indexes(self) -> List[str]:
        """
        遍历时索引列表
        """
        return ['J','K','L'][0:self.dimension]


class InputDataType(BaseDataType):
    @model_validator(mode='after')
    def _post_init(self):
        if not self.var_name:
            if self.name:
                self.var_name = f"in_{self.name}"
            else:
                self.var_name = "in"
        if not self.port_name:
            if self.name:
                self.port_name = f"i_{self.name}_ap"
            else:
                self.port_name = "i_ap"
        return self


class OutputDataType(BaseDataType):
    is_queue: bool = Field(False, description="是否输出队列")
    as_arg: bool = Field(True, description="是否作为参数输出")

    @model_validator(mode='after')
    def _post_init(self):
        if not self.var_name:
            if self.name:
                self.var_name = f"out_{self.name}"
            else:
                self.var_name = "out"
        if not self.port_name:
            if self.name:
                self.port_name = f"o_{self.name}_ap"
            else:
                self.port_name = "o_ap"
        return self

    @property
    def dimension(self) -> int:
        n = super().dimension
        if self.is_queue:
            n += 1
        return n

    @property
    def array_declaration(self) -> str:
        s = super().array_declaration
        if self.is_queue:
            s += '[$]'
        return s


class Transpose(BaseModel):
    enable: bool = Field(False, description="是否启用")
    class_name: str = Field('', description="类名")
    depth: int = Field(16, description="深度")


class IncludeFunction(BaseModel):
    to_twos_complement: bool = Field(False, description="是否添加to_twos_complement函数")
    from_twos_complement: bool = Field(False, description="是否添加from_twos_complement函数")
    cut: bool = Field(False, description="是否添加cut函数")
    slice: bool = Field(False, description="是否添加slice函数")
    transpose: Transpose = Field(default_factory=Transpose, description="transpose函数设置")
    resize: bool = Field(False, description="是否添加resize函数")
    pad: bool = Field(False, description="是否添加填充函数")

    @property
    def is_to_twos_complement_active(self) -> bool:
        return self.to_twos_complement or self.resize

    @property
    def is_from_twos_complement_active(self) -> bool:
        return self.from_twos_complement or self.resize


class BaseCore(BaseModel):
    class_name: str = Field('', description="类名")
    hook_run_name: str = Field('run', description="运行钩子函数名")


class Models(BaseModel):
    """
    has_transpose: 是否需要transpose
    run_output_arguments: 运行函数的输出参数
    run_return: 运行函数的返回参数
    run_output_locals: 运行函数内部输出变量
    is_run_return_queue: 运行函数是否返回队列
    """
    class_prefix: str = Field(..., description="默认类名前缀")
    class_core: str = Field(..., description="实际使用的核心类名")

    class_model: str = Field('', description="模型类名")
    hook_run_name: str = Field('main', description="运行钩子函数名")
    is_run_return_output: str = Field(True, description="运行函数是否通过return的方式输出参数")

    include_function: IncludeFunction = Field(default_factory=IncludeFunction, description="添加函数")
    base_core: BaseCore = Field(default_factory=BaseCore, description="核心")

    input_data_types: List[InputDataType] = Field(..., description="输入数据类型列表")
    output_data_types: List[OutputDataType] = Field(..., description="输出数据类型列表")

    has_transpose: bool = False
    run_output_arguments: List[OutputDataType] = []
    run_return: Optional[OutputDataType] = None
    run_output_locals: List[OutputDataType] = []
    is_run_return_queue: bool = False

    @model_validator(mode='after')
    def _post_init(self):
        if not self.class_model:
            self.class_model = f"{self.class_prefix}model"
        if not self.base_core.class_name:
            self.base_core.class_name = f"{self.class_prefix}base_core"
        if not self.include_function.transpose.class_name:
            self.include_function.transpose.class_name = f"{self.class_prefix}transpose"

        self.render_transpose()
        self.render_run()

        return self

    def render_transpose(self):
        self.has_transpose = self.include_function.transpose.enable

    def render_run(self) -> List[OutputDataType]:
        args = [x for x in self.output_data_types if x.as_arg]

        if self.is_run_return_output and len(args) == 1:
            self.run_return = args[0]
            args = []
        self.run_output_locals = [x for x in self.output_data_types if x not in args]
        self.run_output_arguments = args
        self.is_run_return_queue = self.run_return and self.run_return.is_queue

    def get_run_return_type(self,is_extern:bool=False) -> str:
        """
        运行函数的返回类型

        is extern : 是否是外部函数
        """
        if self.run_return:
            rt = self.run_return.class_name
            if self.is_run_return_queue:
                rt = f"queue_{rt.lower()}"
                if is_extern:
                    rt = f"{self.class_model}::{rt}"
            return rt
        else:
            return 'void'

    def run_argument_declare(self,is_extern:bool) -> str:
        """
        运行函数的参数

        is extern : 是否是外部函数
        """
        args = []
        out_datas = self.run_output_arguments
        has_output = any(out_datas)

        for data in self.input_data_types:
            arg = (
                ('input ' if has_output else '')
                + f'{data.class_name} {data.var_name}{data.array_declaration}'
            )
            args.append(arg)
        for data in out_datas:
            args.append(f'output {data.class_name} {data.var_name}{data.array_declaration}')

        return ','.join(args)

    def run_write_data(self,data:BaseDataType) -> str:
        """
        运行函数输出数据
        """
        name = data.var_name
        if data.dimension:
            condition = (
                f'foreach({name}'
                + ''.join([f'[{x}]' for x in data.indexes])
                + ')'
            )
        else:
            condition = f'if({name})'
        sprint = (
            f'`uvm_info("",$psprintf("output {data.name}'
            + ('[%0d]' * data.dimension if data.depth else '')
            + ':\\n%s",'
            + (','.join([f'{x}' for x in data.indexes]) + ',' if data.indexes else '')
            + name
            + ''.join([f'[{x}]' for x in data.indexes])
            + '.sprint()),UVM_HIGH)'
        )
        write = (
            f'{data.port_name}.write({name}'
            + ''.join([f'[{x}]' for x in data.indexes])
            + ');'
        )
        return f'''
{condition} begin
    {sprint}
    {write}
end
'''.strip()

    def print_data(self,data:BaseDataType,prefix:str) -> str:
        """
        使用sprint打印数据

        prefix: 加在信息前面
        """
        condition = (
            f'foreach({data.var_name}[J])' if data.depth else ''
        ) + (
            f'if({data.var_name}' + ('[J]' if data.depth else '') + ')'
        )
        sprint = (
            f'`uvm_info("",$psprintf("input {data.name}'
            + ('[%0d]' if data.depth else '')
            + ':\\n%s",'
            + ('J,' if data.depth else '')
            + f'{data.var_name}'
            + ('[J]' if data.depth else '')
            + '.sprint()),UVM_HIGH)'
        )
        return f'''
{condition}
    {sprint}
'''.strip()

    def clone_data(self,data:BaseDataType) -> str:
        """
        使用克隆数据
        """
        condition = (
            f'foreach({data.var_name}[J])' if data.depth else ''
        ) + (
            f'if({data.var_name}' + ('[J]' if data.depth else '') + ')'
        )
        sprint = (
            f'$cast({data.var_name}'
            + ('[J]' if data.depth else '')
            + f',{data.var_name}'
            + ('[J]' if data.depth else '')
            + '.clone());'
        )
        return f'''
{condition}
    {sprint}
'''.strip()

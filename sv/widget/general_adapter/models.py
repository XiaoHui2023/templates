from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class DataType(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="数据类型的名字；可省略。为空时默认输出端口名为 o_ap（无中间词缀），钩子默认可为 to_out",
    )
    type: str = Field(..., description="输出数据类型名")
    is_queue: bool = Field(False, description="数据是否是队列")
    port_name: str = Field("", description="输出端口名字")
    hook_name: str = Field("", description="钩子函数名字")

    @model_validator(mode="after")
    def _post_init(self):
        if self.name is not None:
            stripped = self.name.strip()
            self.name = stripped if stripped else None
        if not self.port_name:
            self.port_name = "o_ap" if self.name is None else f"o_{self.name}_ap"
        if not self.hook_name:
            self.hook_name = "to_out" if self.name is None else f"to_{self.name}"
        return self


class CustomAdapterAttribute(BaseModel):
    type: str = Field(..., description="SystemVerilog 类型（含 packed 部分），如 int、bit [7:0]")
    name: str = Field(..., description="成员变量名，须为合法标识符")
    reset: bool = Field(
        False,
        description="为真且 default 已给出时，在 reset_phase 将该成员赋为 default",
    )
    default: Optional[str] = Field(
        default=None,
        description="可选；省略表示无初值、reset_phase 中也不自动赋值。标量有值时用于声明处初值。",
    )
    dimensions: List[str] = Field(
        default_factory=list,
        description="非打包维度；空表示标量。元素为维度写法，如 256、8、$（队列）",
    )


class Models(BaseModel):
    """
    # general_adapter

    生成一个 `uvm_component` 适配器：从输入 analysis port 接收事务，按配置调用转换逻辑
    并写出到对应 analysis port。可通过 `custom_attributes` 增加可选成员。

    # 使用方式

    - 配置 `class_adapter`、`class_data`、`data_types` 与端口名。
    - 按「实现输出转换」一节为 `data_types` 中的每一种输出补齐转换函数。
    - 需要额外成员时，配置 `custom_attributes`。

    # ports

    | 端口 | 方向 | 类型 | 说明 |
    | --- | --- | --- | --- |
    | 默认名 `i_ap`（`in_port_name`） | input | `uvm_analysis_port #(输入事务类型)` | 输入事务 |
    | 默认名 `o_<名>_ap`；`name` 省略或为空时为 `o_ap`（各输出 `port_name`） | output | `uvm_analysis_port #(对应输出类型)` | 转换后写出 |

    # 常用函数

    ## `write`

    analysis imp 回调：克隆输入、调用各输出类型转换函数并写出到输出端口。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `data` | input | 输入事务类型 |  | 输入事务句柄 |

    # 实现输出转换

    生成文件里只为每种 `data_types` 提供 `extern function` 声明，**函数体须由你补齐**。在生成类的子类中实现，或在同一组件层次可见的包内实现，链接规则与项目里其它 `extern` 一致即可。

    每个输出的函数名由该项的 `hook_name` 决定；若未配置，`name` 有值时为 `to_<name>`，`name` 省略或为空时为 `to_out`。签名与模板声明一致：第一个参数为输入事务（参数名由 `name_input_data` 配置），第二个为输出，类型为该条的 `type`；若该条 `is_queue` 为真，输出为对应类型的队列。

    `write` 路径会对输入做 `clone` 后调用上述函数，再把结果送到对应的 analysis port；转换逻辑只放在你实现的函数里即可。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | 输入事务参数（默认名见 `name_input_data`） | input | 输入事务类型 |  | 与生成声明中的名称一致 |
    | 输出事务参数（默认名见 `name_output_data`） | output | 该条目的输出类型或队列 |  | 在函数内构造并赋值 |
    """

    class_adapter: str = Field(..., description="adapter组件类名")
    class_data: str = Field(..., description="输入数据类型名")

    name_input_data: str = Field("data_in", description="输入函数数据参数名字")
    name_output_data: str = Field("data_out", description="输出函数数据参数名字")
    in_port_name: str = Field("i_ap", description="输入端口名字")

    data_types: List[DataType] = Field(..., description="数据类型列表")
    custom_attributes: List[CustomAdapterAttribute] = Field(
        default_factory=list,
        description="在 adapter 上额外生成的可复位成员",
    )

    @model_validator(mode="after")
    def _unique_custom_names(self):
        names = [a.name for a in self.custom_attributes]
        if len(names) != len(set(names)):
            raise ValueError("custom_attributes 中 name 必须唯一")
        return self

    @model_validator(mode="after")
    def _unique_port_names(self):
        outs = [d.port_name for d in self.data_types]
        if len(outs) != len(set(outs)):
            raise ValueError(
                "data_types 中 port_name（含按 name 生成的默认值）必须唯一；"
                "多条 name 为空时默认均为 o_ap，请为其中部分显式配置 port_name"
            )
        return self

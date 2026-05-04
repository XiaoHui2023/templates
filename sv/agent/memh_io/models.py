from pydantic import BaseModel, Field


class Models(BaseModel):
    """
    # memh_io

    生成一个可读写 memh 文件的 UVM agent，用来维护一份 64 位地址、8 位数据的稀疏
    memory。通常只需要配置 `class_prefix`。

    # 使用方式

    推荐在环境中保存 `agent.sqr`，把 sequencer 当作 memh 访问句柄使用。

    - 测试或 scoreboard 可直接调用 sequencer API 读写 memory、加载文件或执行比较。

    # ports

    | port | 方向 | 类型 | 说明 |
    | --- | --- | --- | --- |
    | `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 输入 payload 按地址与数据写入 memory（不区分 command） |
    | `o_load_ap` | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 输出 memh 文件加载产生的 payload |

    # config_db

    | key | 类型 | 说明 |
    | --- | --- | --- |
    | `init_file` | `uvm_config_db #(string)` | 非空时：在 `start_of_simulation_phase` 自动 `load_file` 初始化 memory |
    | `dump_file` | `uvm_config_db #(string)` | 非空时：在 `final_phase` 自动调用 `save_file`，将当前 memory 写入该路径 |

    # 常用函数

    ## `load_file`

    加载 memh 文件到 memory，并从 `o_load_ap` 输出本次加载产生的 payload。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `filename` | input | `string` |  | memh 文件路径 |
    | `clear_first` | input | `bit` | `0` | 加载前是否清空当前 memory |

    **返回值：** `bit` — 成功为 1，失败为 0。

    ## `save_file`

    将当前 memory 保存为 memh 文件。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `filename` | input | `string` |  | 输出文件路径 |

    **返回值：** `bit` — 成功为 1，失败为 0。

    ## `write_payload`

    写入 `uvm_tlm_generic_payload`。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `payload` | input | `uvm_tlm_generic_payload` |  | 要写入的 payload |

    ## `read_payload`

    读取 `uvm_tlm_generic_payload`。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `addr` | input | `bit [63:0]` |  | 读取起始地址 |
    | `len` | input | `int` |  | 读取字节数 |
    | `name` | input | `string` | `"memh_payload"` | payload 对象名 |

    **返回值：** `uvm_tlm_generic_payload` — READ command、数据与地址已填入。

    ## `write_data`

    写入字节队列（与生成代码中的 `byte_array_t` 一致，元素为 `bit [7:0]`）。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `addr` | input | `bit [63:0]` |  | 起始地址 |
    | `data` | input | `bit [7:0] $` |  | 要写入的字节队列 |

    ## `read_data`

    读取字节队列。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `addr` | input | `bit [63:0]` |  | 读取起始地址 |
    | `len` | input | `int` |  | 读取字节数 |
    | `default_value` | input | `bit [7:0]` | `'0` | 未命中地址的填充值 |

    **返回值：** `bit [7:0] $` — 长度 `len` 的字节队列。

    ## `write_byte`

    写入单字节。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `addr` | input | `bit [63:0]` |  | 字节地址 |
    | `data` | input | `bit [7:0]` |  | 要写入的字节 |

    ## `read_byte`

    读取单字节。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `addr` | input | `bit [63:0]` |  | 字节地址 |
    | `default_value` | input | `bit [7:0]` | `'0` | 未命中地址的返回值 |

    **返回值：** `bit [7:0]` — 读取到的字节或 `default_value`。

    ## `compare_file`

    与 memh 文件比较，失败时上报 `uvm_error`。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `filename` | input | `string` |  | 期望 memh 文件路径 |

    **返回值：** `bit` — 完全一致为 1，否则为 0。

    ## `compare_memory`

    与期望 memory 比较，失败时上报 `uvm_error`。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `expected` | ref | `memory` |  | 期望 memory |
    | `expected_name` | input | `string` | `"expected"` | 期望 memory 名称 |

    **返回值：** `bit` — 完全一致为 1，否则为 0。

    ## `clear`

    清空当前 memory。
    """

    class_prefix: str = Field("memh_", description="默认类名的前缀")
    input_port_name: str = Field("i_ap", description="输入 payload 的 analysis port 名字")
    output_port_name: str = Field("o_load_ap", description="输出文件加载 payload 的 analysis port 名字")
    memh_max_bytes_per_line: int = Field(
        16,
        ge=1,
        description="写出 memh 时每行最多包含的连续字节数",
    )

from pydantic import BaseModel, Field


class Models(BaseModel):
    """
    # reg_io

    生成通过 CSV 描述寄存器写事务的 UVM agent：两列分别为点分路径（相对基块）
    与数值（支持常见十六进制与十进制写法）。推荐把 **sequencer** 当作对外 SDK
    句柄使用。

    # 使用方式

    在环境中通过 `uvm_config_db` 设置基寄存器块与可选的初始化 CSV、落盘 CSV
    路径；连接 `i_ap` 与 `o_ap` 上的 `uvm_tlm_generic_payload` 分析端口。初始化
    与中途可调用 sequencer 的 `load_csv` 将行转为写事务并从 `o_ap` 发出；同时
    按配置写回 RAL 并累积落盘记录。`dump_file` 非空时，在 **final_phase** 将累积
    记录写出为 CSV。

    # ports

    | port | 方向 | 类型 | 说明 |
    | --- | --- | --- | --- |
    | `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 外部写事务输入；可解析并写回 RAL，并在配置了 `dump_file` 时记入落盘队列 |
    | `o_ap` | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 由 CSV 加载或 `load_csv` 产生的写事务输出 |

    # config_db

    | key | 类型 | 说明 |
    | --- | --- | --- |
    | `reg_block` | `uvm_reg_block` | 点分路径解析与地址编码的**起始寄存器块**（必填） |
    | `reg_map` | `string` | 可选；非空时使用该名字的 `uvm_reg_map`，否则使用基块的默认 map |
    | `init_file` | `string` | 非空时：在 `start_of_simulation_phase` 自动 `load_csv` |
    | `dump_file` | `string` | 非空时：在 `final_phase` 将累积的寄存器写记录写出为 CSV |

    # 常用函数

    ## `load_csv`

    读取 CSV 并逐行解析为寄存器写：写 RAL、推入落盘队列、从 `o_ap` 发出对应
    payload。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `filename` | input | `string` |  | CSV 路径 |
    | `clear_dump_first` | input | `bit` | `0` | 为 1 时先清空落盘累积队列再加载 |

    **返回值：** `bit` — 成功为 1，失败为 0。

    ## `clear_dump_rows`

    清空当前累积的 CSV 落盘记录（不影响 RAL 镜像）。

    ## `append_dump_row`

    向落盘队列追加一行（路径与数值文本），便于测试手写记录。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `path` | input | `string` |  | 点分寄存器路径 |
    | `value_text` | input | `string` |  | 与 CSV 第二列同风格的数值字符串 |

    ## `row_to_payload`

    将单行 CSV 记录转为 `uvm_tlm_generic_payload`（不写 RAL、不记 dump）。

    | 参数 | 方向 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `row` | input | `csv_row_t` |  | 路径与数值文本 |
    | `payload` | output | `uvm_tlm_generic_payload` |  | 输出 payload 句柄 |

    **返回值：** `bit` — 成功为 1，失败为 0。
    """

    class_prefix: str = Field("reg_io_", description="生成类名前缀（须非空）")
    input_port_name: str = Field("i_ap", description="外部写事务 analysis port 名")
    output_port_name: str = Field("o_ap", description="CSV 加载写事务输出的 analysis port 名")

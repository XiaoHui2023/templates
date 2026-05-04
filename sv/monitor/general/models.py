from pydantic import BaseModel, Field


class Models(BaseModel):
    """
    # General Monitor

    将带 `valid` 的并行数据总线采样结果打成 `uvm_tlm_generic_payload`，经可配置名称的 TLM 分析端口输出，供 scoreboard、参考模型等订阅。

    # Usage

    - 在环境中例化本 monitor，用 `uvm_config_db` 设置与 DUT 绑定的 `virtual` 接口（见下表键名 `if`）。
    - 将分析端口（默认名 `o_ap`）连到下游的 `uvm_subscriber` 或 `uvm_analysis_export` 等；若重命名输出端口，请与 `output_ap_name` 一致并完成连接。
    - 载荷为 **写事务**（`UVM_TLM_WRITE_COMMAND`），数据域为小端字节序（与模板原行为一致：先按位流打包再 `reverse`）。
    - 开启 `address_increment` 时，监视器内部维护累加的字节偏移，作为各次 `set_address` 的地址，前后包在地址上连续、不重叠；关闭时地址恒为 0。

    # ports

    | Port | Direction | Type | Usage |
    | --- | --- | --- |
    | 由 `output_ap_name` 决定（默认 `o_ap`） | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 输出采样得到的通用载荷 |

    # config_db

    | Key | Type | Usage |
    | --- | --- | --- |
    | `if` | `uvm_config_db #(virtual <prefix>interface)` | 传入与本 monitor 匹配的虚拟接口，用于 `rx_data` / `rx_count` 采样 |

    生成符号名为：`class_prefix` 后接后缀 `monitor`（监视器）、`interface`（接口）。`class_prefix` 须非空，否则后缀 `interface` 会与关键字冲突。
    """

    class_prefix: str = Field(
        "general_",
        min_length=1,
        description="类名前缀（须非空）；完整类名为前缀接后缀：`monitor`、`interface`。默认 `general_` 以保持与先前默认输出名一致（`general_monitor`、`general_interface`）。",
    )
    output_ap_name: str = Field(
        "o_ap",
        description="TLM 分析端口的实例名与 `new` 时字符串名，须为合法 SystemVerilog 标识符；默认 o_ap。",
    )
    address_increment: bool = Field(
        False,
        description="为真时按已发字节数累加作为下一包的地址；为假时每包地址为 0。",
    )
    if_clk: str = Field(
        "clk",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="接口时钟端口名（合法 SV 标识符）。",
    )
    if_valid: str = Field(
        "valid",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="接口 valid 端口名。",
    )
    if_width: str = Field(
        "width",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="接口随路宽度/有效位数端口名（原 `bits`/`width` 语义，默认 `width`）。",
    )
    if_data: str = Field(
        "data",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="接口数据向量端口名。",
    )
    data_width_expr: str = Field(
        "UVM_HDL_MAX_WIDTH*16",
        min_length=1,
        strip_whitespace=True,
        description="数据端口位宽常量表达式：`if_data` 为 `[ expr - 1 : 0 ]`，监视器默认参数 DW 与同式对齐。",
    )

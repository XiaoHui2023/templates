# kit_sequencer

`kit_sequencer` 是 `sequencer` 的便捷 facade。

它只负责创建 req/seq、补默认参数、启动 sequence、检查返回状态是否成功。不要在 `kit_sequencer` 中实现寄存器配置、传输执行、scoreboard 比较或 callback 行为。

## 传输配置入参

flash 相关快捷入口可以输入单次传输配置。所有配置入参都有 Python model 生成的默认值。

| 参数 | 说明 |
| --- | --- |
| `io_lanes` | 本次传输使用 1/2/4 线。 |
| `speed_multiplier` | 本次传输使用 1/2/4 倍速。 |
| `spi_mode` | SPI mode 0-3。 |
| `data_frame_bits` | 数据帧位宽。 |
| `cs_id` | 片选编号。 |
| `addr_bytes` | flash 地址阶段字节数。 |
| `use_dma` | 仅在 Python 开启内部或外部 DMA 时生成，默认 0。 |
| `awlen` | 仅内部 DMA 生成，内部 DMA 写突发长度，默认 0。 |
| `arlen` | 仅内部 DMA 生成，内部 DMA 读突发长度，默认 0。 |
| `axi_addr` | 仅内部 DMA 生成，DMA 访问系统内存的 AXI buffer 地址，默认 0。 |

每个 flow/test 快捷入口在 sequence 字段中创建 `host_configuration`，把这些入参作为 inline constraint 参与 randomize。operation 快捷入口仍按 operation req/rsp 三件套传参。标准/增强模式仍由 configuration 约束根据默认值和倍速关系决定。

DMA 入口由 Python 配置裁剪：`internal_dma` 和 `external_dma` 不能同时开启；两者都关闭时 kit API 不出现 DMA 参数。

## 快捷入口

### `init_registers`

根据一个 `transfer_req` 生成并写入本次传输需要的寄存器配置。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `transfer_req` | `dw_spi_transfer_req` | 本次传输的协议形态和 payload |

### `flash_write`

启动 flash 写 flow。地址是 flash/model 地址，不是寄存器地址。`data` 必须非空；空队列不是合法 program 数据。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `address` | `bit [31:0]` | flash 起始地址 |
| `data` | `bit [7:0] $` | 非空写入数据 |
| `io_lanes` | `int` | 可选传输配置 |
| `speed_multiplier` | `int` | 可选传输配置 |
| `spi_mode` | `int` | 可选传输配置 |
| `data_frame_bits` | `int` | 可选传输配置 |
| `cs_id` | `int` | 可选传输配置 |
| `addr_bytes` | `int` | 可选传输配置 |
| `use_dma` | `bit` | 可选传输配置 |
| `awlen` | `bit [7:0]` | 可选内部 DMA 写突发长度 |
| `arlen` | `bit [7:0]` | 可选内部 DMA 读突发长度 |
| `axi_addr` | `bit [31:0]` | 可选 DMA AXI buffer 地址 |

### `flash_read`

启动 flash 读 flow。读回数据不从 kit API 输出；flow sequence 的返回字段和 scoreboard 路径负责校验。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `address` | `bit [31:0]` | flash 起始地址 |
| `length` | `int` | 读长度 |
| `io_lanes` | `int` | 可选传输配置 |
| `speed_multiplier` | `int` | 可选传输配置 |
| `spi_mode` | `int` | 可选传输配置 |
| `data_frame_bits` | `int` | 可选传输配置 |
| `cs_id` | `int` | 可选传输配置 |
| `addr_bytes` | `int` | 可选传输配置 |
| `use_dma` | `bit` | 可选传输配置 |
| `awlen` | `bit [7:0]` | 可选内部 DMA 写突发长度 |
| `arlen` | `bit [7:0]` | 可选内部 DMA 读突发长度 |
| `axi_addr` | `bit [31:0]` | 可选 DMA AXI buffer 地址 |

### `check_clocks`

启动可选时钟检查 operation。kit 内部检查 rsp，失败时 fatal，不输出 result。

默认检查 `hclk` 和 `ssi_clk` 是否高于各自最低频率 24MHz，容差 1%。`ssi_clk` 是控制器输入时钟；check_clock 不检查 `sclk_out`，也不会检查 `hclk` 与 `ssi_clk` 的频率关系。

### `rw_test`

启动读写测试场景：写入数据、读回数据，并把结果交给 scoreboard 自动比较。

`address` 默认是 0。`write_data` 默认是空队列；空队列表示随机生成一段写入数据，长度由 Python 配置 `default_rw_data_bytes` 决定，默认 256 字节。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `address` | `bit [31:0]` | flash 起始地址，默认 0 |
| `write_data` | `bit [7:0] $` | 写入数据；空队列表示随机数据 |
| `io_lanes` | `int` | 可选传输配置 |
| `speed_multiplier` | `int` | 可选传输配置 |
| `spi_mode` | `int` | 可选传输配置 |
| `data_frame_bits` | `int` | 可选传输配置 |
| `cs_id` | `int` | 可选传输配置 |
| `addr_bytes` | `int` | 可选传输配置 |
| `use_dma` | `bit` | 可选传输配置 |
| `awlen` | `bit [7:0]` | 可选内部 DMA 写突发长度 |
| `arlen` | `bit [7:0]` | 可选内部 DMA 读突发长度 |
| `axi_addr` | `bit [31:0]` | 可选 DMA AXI buffer 地址 |

## 边界

`kit_sequencer` 不提供通用 `reg_write` / `reg_read`。寄存器地址、通用读写策略、寄存器查找都由 regmodel 托管；DW SPI sequence/core 只在具体操作里设置明确的大写 REG/FIELD，并由所属 REG `read/write`。

`kit_sequencer` 不输出 `actual_read_data` 或 result。测试 sequence 会把读写结果送到 scoreboard，scoreboard 用内部 mem mirror 自动校验。

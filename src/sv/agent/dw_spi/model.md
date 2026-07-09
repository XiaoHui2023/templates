# model

`model` 目录只定义数据契约，不放执行逻辑。

执行逻辑放在 sequence 或 core：sequence 决定何时做初始化、读写、检查；core 承载可复用工具类；sequencer 只保存基础句柄；kit_sequencer 只封装快捷启动。

## 文件职责

| 文件 | 类 | 职责 |
| --- | --- | --- |
| `spec.sv` | `dw_spi_spec#(type T)` | 族级 enum、localparam、常量定义夹层。 |
| `settings.sv` | `dw_spi_settings` | agent/sequencer 共享的运行期配置和句柄。 |
| `transfer_configuration.sv` | `dw_spi_transfer_configuration` | 单次传输的协议形态配置包。 |
| `host_configuration.sv` | `dw_spi_host_configuration` | 主机侧单次传输配置包，约束 `host_mode == MASTER`。 |
| `slave_configuration.sv` | `dw_spi_slave_configuration` | 从机侧单次传输配置包，约束 `host_mode == SLAVE`。 |
| `configuration.sv` | `dw_spi_configuration` | 单次寄存器字段配置包。 |

## 继承关系

`spec` 是参数化夹层：

```systemverilog
class dw_spi_spec#(type T = uvm_object) extends T;
```

需要使用 SPI 族级 enum 或常量的类继承 `dw_spi_spec#(...)`：

```text
uvm_object
  -> dw_spi_spec#(uvm_object)
    -> dw_spi_settings
    -> core tool classes

uvm_sequence_item
  -> dw_spi_spec#(uvm_sequence_item)
    -> dw_spi_transfer_configuration
      -> dw_spi_host_configuration
      -> dw_spi_slave_configuration
    -> dw_spi_configuration
    -> operation req/rsp
```

继承后类内直接写 `MASTER`、`FLASH_SPI`、`ENHANCED`、`EEPROM_READ`，不要写 `settings::` 或 `spec::`。`settings::type_id::create` 是 UVM factory 用法，不属于 enum/constant 命名空间。

凡是作为 operation req/rsp 或传输配置包传播的数据包，统一继承 `dw_spi_spec#(uvm_sequence_item)`。flow/test 扁平化为单文件 sequence，输入字段和返回字段直接放在 sequence 类中。运行期 settings、mem、register_access 这类工具或共享对象才继承 `dw_spi_spec#(uvm_object)`。

## `spec.sv`

`spec` 保存模块族共享定义：

| 定义 | 用途 |
| --- | --- |
| `host_mode_e` | 主机/从机模式：`MASTER`、`SLAVE`。 |
| `protocol_e` | 传输协议：`GENERAL_SPI`、`FLASH_SPI`。 |
| `frame_mode_e` | 标准/增强模式：`STANDARD`、`ENHANCED`。 |
| `ssi_variant_e` | 控制器变体：`PSSI`、`HSSI`。 |
| `transfer_mode_e` | 传输方向：`TX_AND_RX`、`TX_ONLY`、`RX_ONLY`、`EEPROM_READ`。 |
| `CTRLR0_SPI_FRF_*` | DesignWare `CTRLR0.SPI_FRF` 编码。 |
| `SR_*` | `SR` 状态位索引。 |
| `ISR_DONES` | `ISR.DONES` 位索引。 |
| `MEMH_MAX_BYTES_PER_LINE` | memh 解析时单行最大字节数。 |

## `settings.sv`

`settings` 是 sequencer 持有的运行期共享对象。sequence 通过 `p_sequencer.settings` 读取。

agent 可以不从 `config_db` 输入 settings。未输入时，agent 创建一个 settings、执行 `randomize()`，并用 `UVM_LOW` 打印最终配置。

| 字段 | 用途 |
| --- | --- |
| `ssi_variant` | `core/register_access.sv` 根据 PSSI/HSSI 选择需要设置的 `CTRLR0` FIELD。 |
| `target_sclk_hz` | 目标串行输出频率；`BAUDR` 由测量到的 `ssi_clk` 和该目标频率推导。 |
| `fifo_depth_bytes` | FIFO 阈值约束和默认值边界。默认 32 字节。 |
| `min_hclk_hz` | optional clock check 的 `hclk` 最低频率，默认 24MHz。 |
| `min_ssi_clk_hz` | optional clock check 的 `ssi_clk` 最低频率，默认 24MHz。 |
| `clock_check_tolerance_ppm` | optional clock check 的频率容差，默认 1%。 |
| `interrupt_timeout_ssi_clk_cycles` | transfer 等待 `intr` 的 `ssi_clk` 周期上限，超时直接 `uvm_fatal`。 |
| `default_tx_fifo_threshold` | 默认 TX FIFO threshold。 |
| `default_rx_fifo_threshold` | 默认 RX FIFO threshold。 |
| `default_rx_sample_delay_ns` | 默认 `RX_SAMPLE_DELAY`。 |
| `regmodel` | UVM RAL 句柄。寄存器访问使用大写 REG/FIELD，例如 `settings.regmodel.CTRLR0`。 |
| `vif` | top interface 句柄，用于中断、时钟测量、可选子 interface。 |

`settings` 不保存单次传输协议形态，不保存 flash 几何信息。

已移出或删除的字段：

| 字段 | 处理 |
| --- | --- |
| `default_protocol` | 删除。协议属于 sequence req 或 operation req。 |
| `default_frame_mode` | 移到 per-transfer configuration。 |
| `default_io_lanes` | 移到 per-transfer configuration。 |
| `flash_size_bytes` | 删除。scoreboard mem 是动态 byte queue。 |
| `flash_page_size` | 删除。不模拟页擦写。 |
| `flash_erase_value` | 删除。mem 按加载和写入动态扩展。 |

## `transfer_configuration.sv`

`transfer_configuration` 是单次读写传输的协议形态配置包，作为 sequence req 传播。

| 字段 | 用途 |
| --- | --- |
| `host_mode` | 主机/从机模式；影响 `CTRLR0.SSI_IS_MST` 和 sequence 行为。 |
| `frame_mode` | 标准/增强模式；增强模式允许 2/4 倍速。 |
| `io_lanes` | 1/2/4 线传输选择。 |
| `speed_multiplier` | 1/2/4 倍速；映射到 `CTRLR0.SPI_FRF`。 |
| `use_dma` | 仅在 Python 开启内部或外部 DMA 时生成；默认约束为 0。 |
| `awlen` | 仅内部 DMA 生成；builder 转成 `awlen << 8` 后配置 `AXIAWLEN.AWLEN`。 |
| `arlen` | 仅内部 DMA 生成；builder 转成 `arlen << 8` 后配置 `AXIARLEN.ARLEN`。 |
| `axi_addr` | 仅内部 DMA 生成，写入 `AXIAR0.AXIAR0`。 |
| `spi_mode` | SPI mode 0-3；用于 CPOL/CPHA 相关配置。 |
| `data_frame_bits` | 每帧数据位宽。 |
| `cs_id` | 片选编号；用于 `SER` 和 callback 控制。 |
| `addr_bytes` | flash 地址阶段字节数。 |
| `dummy_cycles` | flash read dummy cycle 数。 |

这些字段是 `rand`，默认值由 Python 配置生成 soft constraint。主机测试默认创建 `host_configuration`，从机测试可显式创建 `slave_configuration`。

DMA 生成模式由 Python `internal_dma` 和 `external_dma` 决定，二者不能同时为 true。两者都为 false 时不生成 DMA 字段和 DMA 寄存器配置。

`rw_test_seq` 的 `address` 默认约束为 0。`write_data` 为空时，test sequence 会随机生成一段数据；长度由 Python 配置 `default_rw_data_bytes` 生成，默认 256 字节。

## `configuration.sv`

`configuration` 是单次寄存器字段配置包，用来承载一次 init/apply 需要写入 regmodel FIELD 的值。

| 字段 | 用途 |
| --- | --- |
| `host_mode` | 配置 `CTRLR0.SSI_IS_MST`。 |
| `transfer_mode` | 配置 `CTRLR0.TMOD`。 |
| `spi_frf` | 配置 `CTRLR0.SPI_FRF`。 |
| `spi_ctrlr0_en` | 增强模式下写 `SPI_CTRLR0`。 |
| `wait_cycles` | 配置 `SPI_CTRLR0.WAIT_CYCLES`；增强读默认来自 `dummy_cycles`，常用 8 拍。 |
| `inst_l` | 配置 `SPI_CTRLR0.INST_L`。 |
| `addr_l` | 配置 `SPI_CTRLR0.ADDR_L`。 |
| `trans_type` | 配置 `SPI_CTRLR0.TRANS_TYPE`；当前增强 flash flow 使用 instruction 标准、address 按 `SPI_FRF` 的格式。 |
| `spi_mode` | 配置 `CTRLR0.SCPOL/SCPH`。 |
| `data_frame_bits` | 配置 `CTRLR0.DFS`。 |
| `ndf` | 配置 `CTRLR1.NDF`，单位是 DFS frame，不是 byte。 |
| `ssi_en` | 配置 `SSIENR.SSIC_EN`。 |
| `ser` | 配置 `SER.SER` 片选 mask。 |
| `baudr` | 配置 `BAUDR.SCKDV`；该值由 `ssi_clk` 和目标串行输出频率推导。 |
| `txftlr` | 配置 `TXFTLR.TFT`。 |
| `rxftlr` | 配置 `RXFTLR.RFT`。 |
| `txeim/txoim/rxuim/rxoim/rxfim/mstim` | 配置 `IMR` 各中断 mask field。 |
| `dmatdl` | 仅 DMA 模式生成，配置 `DMATDLR.DMATDL`。 |
| `dmardl` | 仅 DMA 模式生成，配置 `DMARDLR.DMARDL`。 |
| `rdmae/tdmae` | DMA 生成时配置 `DMACR.RDMAE/TDMAE`；内部 DMA 也按传输方向打开握手位。 |
| `write_internal_dma_regs` | 仅内部 DMA 生成，控制是否写 `AXIAWLEN/AXIARLEN/SPIDR/SPIAR/AXIAR0`。 |
| `idmae` | 仅内部 DMA 生成，配置 `DMACR.IDMAE`。 |
| `ainc` | 仅内部 DMA 生成，配置 `DMACR.AINC`。 |
| `awlen` | 配置 `AXIAWLEN.AWLEN`，内部 DMA 使用 `awlen << 8` 后的寄存器字段值。 |
| `arlen` | 配置 `AXIARLEN.ARLEN`，内部 DMA 使用 `arlen << 8` 后的寄存器字段值。 |
| `spi_inst` | 配置 `SPIDR.SPI_INST`，来自当前 transfer opcode。 |
| `sdar` | 配置 `SPIAR.SDAR`，来自 payload address 的低 32 bit。 |
| `axiar0` | 配置 `AXIAR0.AXIAR0`，来自 `axi_addr`。 |
| `rx_sample_delay` | 配置 `RX_SAMPLE_DELAY.RSD`。 |
| `write_rx_sample_delay` | 是否写 `RX_SAMPLE_DELAY`。 |

`configuration` 可以引用 `settings` 做约束，例如默认分频、FIFO threshold、rx sample delay。它不保存寄存器地址，也不保存拼好的完整寄存器值；寄存器地址和 bit layout 由 regmodel/FIELD 托管。实际读写只能通过大写 REG/FIELD 的 regmodel 句柄完成。

## 与 scoreboard/mem 的边界

scoreboard 的 `mem` 在 `core/mem.sv`，不是 `model` 类型。

`mem` 使用动态 `bit [7:0]` queue：

- 加载 memh 或 `.hex` 文件时按实际数据长度扩展。
- 写入超过当前长度时自动扩展。
- 读取或比较超过当前有效长度时报错。
- 不需要 flash size、page size、erase value。

sequence 从真实读写路径拿到数据后，把地址和 byte queue 送入 scoreboard；scoreboard 用内部 mem mirror 做及时比较。

## 禁放内容

`model` 内不要放这些内容：

- 寄存器地址常量。
- regmodel read/write task。
- CS 开关、等待中断、等待 busy 清零等执行动作。
- scoreboard 比较逻辑。
- memh/`.hex` 文件解析逻辑。
- sequencer/kit_sequencer 快捷函数。

重复寄存器 FIELD apply 流程放在 `core/register_access.sv` 的实例化工具类中，但寄存器访问必须直接写 `settings.regmodel.<REG>.read(status, data)`、`settings.regmodel.<REG>.<FIELD>.set(...)` 和 `settings.regmodel.<REG>.write(status, settings.regmodel.<REG>.get())`，不使用 `update()`，不再封装 `set_field/get_field/update_reg`。从 operation req 生成 `configuration` 的入口放在 operation sequence 中。

## Interrupt Timeout Settings

`interrupt_timeout_ssi_clk_cycles` 是 transfer 等待 `intr` 的周期上限。

interface 会同时使用 `min_ssi_clk_hz` 和 `clock_check_tolerance_ppm` 推导一个仿真时间兜底超时。这样既能覆盖正常慢响应，也能覆盖 `ssi_clk` 停住导致周期计数不前进的情况。

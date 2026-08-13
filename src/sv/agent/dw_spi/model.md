# Model

`model` 目录只定义数据契约，不放执行逻辑。执行逻辑放在 sequence 或 core；sequencer 只保存基础句柄；kit_sequencer 只封装快捷启动。

## 文件职责

| 文件 | 类 | 职责 |
| --- | --- | --- |
| `settings.sv` | `dw_spi_settings` | agent/sequencer 共享运行期配置和句柄 |
| `transfer_configuration.sv` | `dw_spi_transfer_configuration` | 单次传输协议形态配置包 |
| `host_configuration.sv` | `dw_spi_host_configuration` | 主机侧单次传输配置包 |
| `slave_configuration.sv` | `dw_spi_slave_configuration` | 从机侧单次传输配置包 |
| `configuration.sv` | `dw_spi_configuration` | 单次寄存器 FIELD 配置包 |
| `flash_command/*.sv` | `dw_spi_*_flash_command` | SPI flash 指令配置包；具体 NOR/NAND/XIP/厂商 opcode 各自独立文件 |

## `settings.sv`

`settings` 由 sequencer 持有，sequence 通过 `p_sequencer.settings` 读取。agent 可以不从 `config_db` 输入 settings；未输入时 agent 创建一个、`randomize()`，并用 `UVM_LOW` 打印最终配置。

| 字段 | 用途 |
| --- | --- |
| `ssi_variant` | 选择 PSSI/HSSI 相关 FIELD 集合 |
| `default_cs_control_mode` | 单次传输配置的片选控制默认值，默认 `HARDWARE_CS` |
| `default_completion_mode` | 单次传输的完成等待默认策略，默认 `PREFER_INTERRUPT_COMPLETION` |
| `target_sclk_hz` | 目标串行输出频率，用于从 `ssi_clk` 推导 `BAUDR` |
| `fifo_depth_bytes` | FIFO 深度，默认 32 字节 |
| `min_hclk_hz` / `min_ssi_clk_hz` | optional clock check 最低频率 |
| `clock_check_tolerance_ppm` | optional clock check 容差 |
| `interrupt_timeout_margin_percent` | 单次 transfer 理论耗时的百分比余量 |
| `interrupt_timeout_extra_ssi_clk_cycles` | 单次 transfer 理论耗时的固定余量 |
| `fifo_status_timeout_ssi_clk_cycles` | 单次等待 `SR.TFNF` 或 `SR.RFNE` 的短轮询上限 |
| `ctrlr1_ndf_max` | `CTRLR1.NDF` 编码值上限，默认 `65535`，对应实际最多 `65536` 个 frame |
| `default_tx_fifo_threshold` / `default_rx_fifo_threshold` | 默认 FIFO threshold |
| `default_rx_sample_delay_ns` | 默认 `RX_SAMPLE_DELAY` |
| `regmodel` | UVM RAL 句柄，使用大写 REG/FIELD |
| `vif` | top interface 句柄 |

`settings` 不保存单次传输协议形态，也不保存 flash size、page size、erase value。scoreboard mem 是动态 byte queue。

## `transfer_configuration.sv`

`transfer_configuration` 是单次读写传输的协议形态配置包，作为 sequence req 传播。

| 字段 | 用途 |
| --- | --- |
| `host_mode` | 主机/从机模式 |
| `frame_mode` | 标准/enhanced 模式 |
| `cs_control_mode` | 本次片选控制模式 |
| `io_lanes` | 1/2/4 线传输选择 |
| `speed_multiplier` | 1/2/4 倍速，映射到 `CTRLR0.SPI_FRF` |
| `use_dma` | 仅在 Python 开启内置或外部 DMA 时生成，默认 0 |
| `awlen` / `arlen` / `axi_addr` | 仅内置 DMA 生成 |
| `spi_mode` | SPI mode 0-3 |
| `data_frame_bits` | 每帧数据位宽 |
| `cs_id` | `SER` 和 callback 使用的片选编号 |
| `addr_bytes` | flash address phase 字节数 |

这些字段是 `rand`，默认值由 Python 配置生成 soft constraint。`SOFTWARE_CS` 只支持主机 1x standard；enhanced、2x、4x 约束为硬件 CS。

operation transfer req 还会携带 `instruction_lanes` 和 `address_lanes`，分别描述 instruction/address phase 线宽。这两个字段不是用户级默认配置，而是由 flash command packet 按 opcode 填入：QPP `0x32` 的 instruction/address 均为单线，只有 payload 为 4 线；`READ2X 0xBB` 使用单线 instruction、2 线 address；`READ4X 0xEB` 使用单线 instruction、4 线 address；其余当前内置指令使用单线 instruction。`register_config_builder` 根据两个相位线宽推导 `SPI_CTRLR0.TRANS_TYPE` 和 timeout。

Python `internal_dma` 和 `external_dma` 互斥。两者都为 false 时，不生成 DMA 字段和 DMA 寄存器配置。

## `flash_command/*.sv`

flash 指令包见 [flash_command.md](model/flash_command.md)。每个指令包只写本 opcode 的协议形态约束；flow sequence 通过 `flash_command_adapter` 把指令包转换为通用 `transfer_req`，再交给 `transfer_seq` 执行。不要在 flow 里散写 opcode、address lane、dummy、TMOD、memory mirror 更新等规则。

接收整形和前置流程也由指令包声明：`rx_skip_bytes` 表示实际接收后需要丢弃的前导 byte 数，`requires_qe` 表示执行该指令前是否运行 QE 配置流程。flow 只消费这些字段，不根据速度或 opcode 再次推导。Enhanced 1x 使用 `FASTREAD1X 0x0B`；`READ2X 0xBB` 配置 `rx_skip_bytes=addr_bytes`；`READ4X 0xEB` 配置 `dummy_cycles=6`、`rx_skip_bytes=3`、`requires_qe=1`。

## `configuration.sv`

`configuration` 是单次寄存器 FIELD 配置包，用来承载一次 apply 需要写入 regmodel FIELD 的值。它不保存寄存器地址，也不保存拼好的完整寄存器值；寄存器地址和 bit layout 由 regmodel/FIELD 托管。

| 字段 | 用途 |
| --- | --- |
| `host_mode` | 配置 `CTRLR0.SSI_IS_MST` |
| `transfer_mode` | 配置 `CTRLR0.TMOD` |
| `spi_frf` | 配置 `CTRLR0.SPI_FRF` |
| `spi_ctrlr0_en` | enhanced 模式下写 `SPI_CTRLR0` |
| `wait_cycles` / `inst_l` / `addr_l` / `trans_type` | 配置 `SPI_CTRLR0` |
| `spi_inst` / `sdar` | enhanced 模式或内部 DMA 寄存器配置开启时，配置 `SPIDR.SPI_INST` / `SPIAR.SDAR` |
| `spi_clk_stretch_en` | enhanced 模式下配置 `SPI_CTRLR0.CLK_STRETCH_EN`，保护 RX/DMA/FIFO 数据流 |
| `spi_mode` / `data_frame_bits` | 配置 `CTRLR0` CPOL/CPHA/DFS |
| `sste` | 配置 `CTRLR0.SSTE`，当前约束为 0，避免帧间自动 toggle 破坏收发连续性 |
| `actual_data_frames` / `ndf` | data phase 的实际 frame 数，以及 `CTRLR1.NDF` 编码值。instruction/address/dummy 不计入；非零 data frame 数编码为 `actual_data_frames - 1` |
| `ssi_en` / `ser` / `baudr` | 配置 `SSIENR`、`SER`、`BAUDR` |
| `txftlr` / `rxftlr` | 配置 FIFO threshold |
| `txeim/txoim/rxuim/rxoim/rxfim/mstim` | 配置 `IMR` FIFO/error mask |
| DMA 字段 | 仅在 Python DMA 生成时存在 |
| `rx_sample_delay` / `write_rx_sample_delay` | 配置 `RX_SAMPLE_DELAY` |
| `completion_mode` | 本次完成等待策略 |
| `interrupt_timeout_ssi_clk_cycles` | 本次完成等待上限 |

## Completion Mode

当前代码以这里为准：

| Value | 行为 |
| --- | --- |
| `PREFER_INTERRUPT_COMPLETION` | 默认模式。内置 DMA 且 `intr` 已连接时等待 top `intr` 并检查 `ISR.DONES`；其他情况轮询 `SR.TFE && !SR.BUSY`。 |
| `INTERRUPT_COMPLETION` | 强制中断模式。只允许内置 DMA transfer；等待 top `intr` 后检查 `ISR.DONES`。非内置 DMA 会 fatal。 |
| `POLLING_COMPLETION` | 强制轮询 `SR.TFE && !SR.BUSY`。 |

`TXEIM/RXFIM` 等 FIFO interrupt mask 不代表 transfer done。非 DMA PIO 如果要使用中断降低 CPU 占用，需要单独实现 FIFO IRQ 驱动状态机。

## Scoreboard / Mem 边界

scoreboard 的 `mem` 在 `core/mem.sv`，不是 model 类型。`mem` 使用动态 `bit [7:0]` queue：加载 memh 或 `.hex` 时按实际数据长度扩展，写入越界时自动扩展，读取或比较越过当前长度时报错。

sequence 从真实读写路径拿到数据后，把地址和 byte queue 送入 scoreboard；scoreboard 用内部 mem mirror 做及时比较。

## Flash Command Compatibility

`flash_command/*.sv` 是 SPI flash 指令配置包体系，不是单一 SPI NOR 型号模型。基础层保持通用，只描述 opcode/address/dummy/data transaction；具体 NOR、NAND、XIP、厂商扩展命令分别放在独立指令包里。默认 `flash_read` / `flash_write` / `rw_test` 是 NOR-like 便捷 flow，默认 3-byte address，可配置为 4-byte address。控制器 agent 不推断挂载的 flash 类型，也不把所有 `FLASH_SPI` transfer 强制成 3/4-byte address。

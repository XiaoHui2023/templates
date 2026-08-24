# 计算公式

- **f_ssi**：输入 DesignWare SPI/SSI 控制器的参考时钟频率，单位 Hz。
- **f_sclk_target**：目标串行输出频率，单位 Hz。
- **f_sclk_out**：输出到从机的串行时钟频率，单位 Hz。
- **BAUDR_logical**：按目标波形推导的偶数逻辑分频值，取值范围 2 到 65534。
- **SCKDV_reg**：实际写入 `BAUDR.SCKDV` 的寄存器编码。

## BAUDR

| 参数 | 说明 |
| --- | --- |
| **f_ssi** | 由 `ssi_clk` 测量得到，必须大于 0。 |
| **f_sclk_target** | 目标串行输出频率，必须大于 0。 |
| **BAUDR_raw** | 初始分频值，向上取整，保证输出频率不超过目标。 |
| **BAUDR_logical** | 偶数逻辑分频值；小于 2 时取 2，奇数时加 1。 |
| **SCKDV_reg** | 非 DMA 等于 `BAUDR_logical`；DMA 等于 `BAUDR_logical >> 1`。 |

```text
BAUDR_raw = ceil(f_ssi / f_sclk_target)

BAUDR_min = max(2, BAUDR_raw)

BAUDR_logical = BAUDR_min         when BAUDR_min is even
BAUDR_logical = BAUDR_min + 1     when BAUDR_min is odd

SCKDV_reg = BAUDR_logical         for PIO
SCKDV_reg = BAUDR_logical >> 1    for DMA

f_sclk_out = f_ssi / BAUDR_logical
f_sclk_out = f_ssi / (2 * SCKDV_reg)  for DMA
```

`BAUDR_logical` 由输入时钟和目标输出频率推导，不是固定默认值。当前控制器的 DMA 波形分频是 `SCKDV` 寄存器值的两倍，因此 DMA 只在寄存器编码阶段右移一位；实际波形与超时计算仍使用 `BAUDR_logical`。

## Transfer Interrupt Timeout

中断等待上限按单次 transfer 推导，不使用固定全局周期数。

| 参数 | 说明 |
| --- | --- |
| **inst_bits** | instruction 阶段 bit 数，通常为 `inst_bytes * 8`。 |
| **addr_bits** | address 阶段 bit 数，通常为 `addr_bytes * 8`。 |
| **data_bits** | data 阶段 bit 数，通常为 `payload_bytes * 8`。 |
| **width_inst** | instruction 阶段每个 sclk 传输的 bit 数；由指令包的 `instruction_lanes` 决定。 |
| **width_addr** | address 阶段每个 sclk 可传输的 bit 数；standard 为 1，enhanced 按本次 `address_lanes`。PP/DPP/QPP 和 output-read 命令为 1，I/O read 命令可为 2/4。 |
| **width_data** | data 阶段每个 sclk 可传输的 bit 数；standard 为 1，enhanced 按本次 `speed_multiplier`。 |
| **dummy_cycles** | 协议 dummy/wait sclk 周期。接收类 enhanced transfer 会映射到 `SPI_CTRLR0.WAIT_CYCLES`；flash write/program flow 强制为 0。 |

当前内置 NOR-like read packet 使用 `03h=0`、`BBh=4`、`EBh=6` 个 SCLK cycle。`READ1X 03h` 固定为 standard 且不使用 dummy cycle；2x/4x enhanced 路径通过 `SPI_CTRLR0` 描述 instruction、address、dummy 和 data phase。

`transfer_req` 按最终控制器模式计算接收前导丢弃量：`EEPROM_READ` 使用 `rx_skip_bytes = dummy_cycles * io_lanes / 8`，其它模式使用 0。`transfer_length = requested_length + rx_skip_bytes`；flow 丢弃前导 byte 后，只把 `requested_length` 个实际数据交给 scoreboard。DMA read 使用 `RX_ONLY`，不丢弃数据。
| **fifo_chunks** | `ceil(max(payload_bytes, 1) / fifo_depth_bytes)`。 |
| **margin_percent** | Python 输入的 `interrupt_timeout_margin_percent`。 |
| **extra_cycles** | Python 输入的 `interrupt_timeout_extra_ssi_clk_cycles`。 |

```text
inst_sclk = ceil(inst_bits / width_inst)

addr_sclk = ceil(addr_bits / width_addr)

data_sclk = ceil(data_bits / width_data)

serial_sclk = max(1, inst_sclk + addr_sclk + dummy_cycles + data_sclk)

base_ssi_cycles = serial_sclk * BAUDR_logical

fifo_chunks = ceil(max(payload_bytes, 1) / fifo_depth_bytes)

fifo_ssi_cycles = fifo_chunks * BAUDR_logical

margin_ssi_cycles = ceil((base_ssi_cycles + fifo_ssi_cycles) * margin_percent / 100)

interrupt_timeout_ssi_clk_cycles =
    base_ssi_cycles + fifo_ssi_cycles + margin_ssi_cycles + extra_cycles
```

`fifo_ssi_cycles` 是按 FIFO chunk 给的调度余量，不表示控制器每个 chunk 都一定产生中断。这样小传输能尽早超时，长传输仍按理论串行时间放宽。

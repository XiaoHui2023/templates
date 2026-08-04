# 计算公式

- **f_ssi**：输入 DesignWare SPI/SSI 控制器的参考时钟频率，单位 Hz。
- **f_sclk_target**：目标串行输出频率，单位 Hz。
- **f_sclk_out**：输出到从机的串行时钟频率，单位 Hz。
- **BAUDR**：写入 `BAUDR.SCKDV` 的偶数分频值，取值范围 2 到 65534。

## BAUDR

| 参数 | 说明 |
| --- | --- |
| **f_ssi** | 由 `ssi_clk` 测量得到，必须大于 0。 |
| **f_sclk_target** | 目标串行输出频率，必须大于 0。 |
| **BAUDR_raw** | 初始分频值，向上取整，保证输出频率不超过目标。 |
| **BAUDR** | 偶数分频值；小于 2 时取 2，奇数时加 1。 |

```text
BAUDR_raw = ceil(f_ssi / f_sclk_target)

BAUDR_min = max(2, BAUDR_raw)

BAUDR = BAUDR_min                 when BAUDR_min is even
BAUDR = BAUDR_min + 1             when BAUDR_min is odd

f_sclk_out = f_ssi / BAUDR
```

`BAUDR` 是由输入时钟和目标输出频率推导出的寄存器写入值，不是固定默认值。

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
| **fifo_chunks** | `ceil(max(payload_bytes, 1) / fifo_depth_bytes)`。 |
| **margin_percent** | Python 输入的 `interrupt_timeout_margin_percent`。 |
| **extra_cycles** | Python 输入的 `interrupt_timeout_extra_ssi_clk_cycles`。 |

```text
inst_sclk = ceil(inst_bits / width_inst)

addr_sclk = ceil(addr_bits / width_addr)

data_sclk = ceil(data_bits / width_data)

serial_sclk = max(1, inst_sclk + addr_sclk + dummy_cycles + data_sclk)

base_ssi_cycles = serial_sclk * BAUDR

fifo_chunks = ceil(max(payload_bytes, 1) / fifo_depth_bytes)

fifo_ssi_cycles = fifo_chunks * BAUDR

margin_ssi_cycles = ceil((base_ssi_cycles + fifo_ssi_cycles) * margin_percent / 100)

interrupt_timeout_ssi_clk_cycles =
    base_ssi_cycles + fifo_ssi_cycles + margin_ssi_cycles + extra_cycles
```

`fifo_ssi_cycles` 是按 FIFO chunk 给的调度余量，不表示控制器每个 chunk 都一定产生中断。这样小传输能尽早超时，长传输仍按理论串行时间放宽。

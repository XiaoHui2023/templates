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

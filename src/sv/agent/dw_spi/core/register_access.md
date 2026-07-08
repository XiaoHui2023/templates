# Register Access Flow

`register_access` 是实例化工具类，由 operation sequence 创建并注入 `settings`。它只接收 model 层 `configuration`，不依赖任何 sequence req/rsp 类型。

## 输入

| 对象 | 来源 | 用途 |
| --- | --- | --- |
| `settings.regmodel` | sequencer settings | 提供大写 REG/FIELD 句柄 |
| `configuration` | operation 层 builder | 承载本次要写入的字段值 |

## Apply

1. 检查 `configuration`、`settings`、`settings.regmodel` 非空。
2. 用 `$cast()` 把 configuration 里的枚举值转换成本工具类的枚举类型。
3. 写 `SSIENR.SSIC_EN = 0`，关闭控制器。
4. 配置 `IMR` 并写 `ICR` 清中断。
5. 写 `SER.SER = 0`，释放片选。
6. 根据 `settings.ssi_variant` 选择 PSSI/HSSI 字段集合，配置 `CTRLR0`。
7. 配置 `CTRLR1.NDF`、`BAUDR.SCKDV`、`TXFTLR.TFT`、`RXFTLR.RFT`。
8. DMA 生成模式开启时配置 `DMACR` 和 DMA threshold；内部 DMA 写 `IDMAE/AINC`，外部 DMA 写 `RDMAE/TDMAE`。
9. 内部 DMA 模式下配置 `AXIAWLEN.AWLEN`、`AXIARLEN.ARLEN`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`；外部 DMA 和无 DMA 模式不写这些寄存器。
10. 按 `write_rx_sample_delay` 决定是否配置 `RX_SAMPLE_DELAY.RSD`。
11. 写 `SER.SER` 和 `SSIENR.SSIC_EN`，完成本次配置。

## 注意事项

- 不保存寄存器地址，不维护字符串到寄存器的地址表。
- 不拼接完整寄存器值；直接使用 `settings.regmodel.<REG>.read(status, data)` 刷新镜像，`settings.regmodel.<REG>.<FIELD>.set(...)` 修改字段，再调用 `settings.regmodel.<REG>.write(status, settings.regmodel.<REG>.get())`。
- 不提供通用 `reg_write` / `reg_read` 包装。
- 不声明静态函数集合；sequence 实例化工具对象并注入依赖。
- 不从 core 反向引用 sequence 层类型。
- DMA 寄存器也按明确 FIELD 写入，不使用完整寄存器拼值。
- 不在 core 中封装 `set_field/get_field/update_reg` 这类寄存器访问二次 API；代码必须显式写出具体 REG/FIELD。
- 不使用 `update()`；本模块寄存器总线访问只用 `read()` 和 `write()`。

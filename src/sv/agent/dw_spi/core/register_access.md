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
8. 配置 `DMACR.IDMAE/AINC`、`DMATDLR.DMATDL`、`DMARDLR.DMARDL`。
9. 内部 DMA 模式下配置 `AXIAWLEN.AWLEN`、`AXIARLEN.ARLEN`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`。
10. 按 `write_rx_sample_delay` 决定是否配置 `RX_SAMPLE_DELAY.RSD`。
11. 写 `SER.SER` 和 `SSIENR.SSIC_EN`，完成本次配置。

## 注意事项

- 不保存寄存器地址，不维护字符串到寄存器的地址表。
- 不拼接完整寄存器值；只设置 FIELD，然后更新所属 REG。
- 不提供通用 `reg_write` / `reg_read` 包装。
- 不声明静态函数集合；sequence 实例化工具对象并注入依赖。
- 不从 core 反向引用 sequence 层类型。
- 内部 DMA 寄存器也按明确 FIELD 写入，不使用完整寄存器拼值。

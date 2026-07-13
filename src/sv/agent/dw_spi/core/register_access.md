# Register Access Flow

`register_access` 是实例化工具类，由 operation sequence 创建并注入 `settings`。它只接收 model 层 `configuration`，不依赖任何 sequence req/rsp 类型。

## 输入

| 对象 | 来源 | 用途 |
| --- | --- | --- |
| `settings.regmodel` | sequencer settings | 提供大写 REG/FIELD 句柄；task 内先保存为局部 `rm` |
| `report_context` | operation sequence 注入的 `p_sequencer` | 让 core 工具类的 `UVM_LOW` / `UVM_DEBUG` 跟随 sequencer/agent 的 report verbosity |
| `configuration` | operation 层 builder | 承载本次要写入的字段值 |

## Apply

1. 检查 `configuration`、`settings`、`settings.regmodel` 非空。
2. 用 `$cast()` 把 configuration 里的枚举值转换成本工具类的枚举类型。
3. 写 `SSIENR.SSIC_EN = 0`，关闭控制器。
4. 配置 `IMR` 并写 `ICR` 清中断。
5. 写 `SER.SER = 0`，释放片选。
6. 根据 `settings.ssi_variant` 选择 PSSI/HSSI 字段集合，配置 `CTRLR0`。
7. 配置 `SPI_CTRLR0.WAIT_CYCLES/INST_L/ADDR_L/TRANS_TYPE`（仅增强模式）、`CTRLR1.NDF`、`BAUDR.SCKDV`、`TXFTLR.TFT`、`RXFTLR.RFT`。
8. DMA 生成模式开启时配置 `DMACR` 和 DMA threshold；内部 DMA 写 `RDMAE/TDMAE/IDMAE/AINC`，外部 DMA 写 `RDMAE/TDMAE`。
9. 内部 DMA 模式下配置 `AXIAWLEN.AWLEN = awlen << 8`、`AXIARLEN.ARLEN = arlen << 8`、`SPIDR.SPI_INST`、`SPIAR.SDAR`、`AXIAR0.AXIAR0`；外部 DMA 和无 DMA 模式不写这些寄存器。
10. 按 `write_rx_sample_delay` 决定是否配置 `RX_SAMPLE_DELAY.RSD`。
11. 写 `SER.SER` 和 `SSIENR.SSIC_EN`，完成本次配置。

`IMR/ICR` 阶段只设置中断 mask 并清理旧中断状态，不等待 `intr`，也不轮询 `ISR.DONES`。真正等待 transfer 完成中断的动作在 `sequence/operation/transfer` 中，发生在本函数完成寄存器配置、片选激活、PIO/DMA 启动之后。

PIO 写 DR 时使用 `write_bytes_to_dr()`。flash 协议的 operation sequence 会先把 opcode、地址字节和写 payload 组合成 DR byte stream，再交给 core 写 `DR`；core 不理解 opcode/address 语义，只负责等待 `SR.TFNF` 并逐 byte 写 `DR`。

## 注意事项

- 不保存寄存器地址，不维护字符串到寄存器的地址表。
- 不拼接完整寄存器值；task 内先写 `rm = settings.regmodel`，再使用 `rm.<REG>.read(status, data)` 刷新镜像，`rm.<REG>.<FIELD>.set(...)` 修改字段，最后调用 `rm.<REG>.write(status, rm.<REG>.get())`。
- RAL `read()` / `write()` 的 `status` 只作为 API 形参保留，不做 `UVM_IS_OK` 检查和逐次报错；寄存器模型正确性由环境和 regmodel 自身保证。
- 不提供通用 `reg_write` / `reg_read` 包装。
- 不声明静态函数集合；sequence 实例化工具对象并注入依赖。
- 不从 core 反向引用 sequence 层类型。
- core 工具类不是 `uvm_component` 时，不直接用 `` `uvm_info`` 承担可控调试打印；调用方注入 `uvm_report_object report_context`，工具类内部先调用 `report_context.uvm_report_enabled()`，再用短参数形式调用 `report_context.uvm_report_info(id, message, verbosity)`。这样把 agent/sequencer verbosity 调到 `UVM_DEBUG` 时，core 的 debug 明细也会打开。
- DMA 寄存器也按明确 FIELD 写入，不使用完整寄存器拼值。
- 不在 core 中封装 `set_field/get_field/update_reg` 这类寄存器访问二次 API；代码必须显式写出具体 REG/FIELD。
- 不使用 `update()`；本模块寄存器总线访问只用 `read()` 和 `write()`。

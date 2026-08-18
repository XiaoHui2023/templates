# Register Access Flow

`register_access` 是实例化工具类，由 operation sequence 创建并注入 `settings` 与 `report_context`。它只接收 model 层 `configuration`，不依赖任何 sequence req/rsp 类型。

## Apply

1. 检查 `configuration`、`settings`、`settings.regmodel` 非空。
2. 用 `$cast()` 把 configuration 里的枚举值转换成本工具类的枚举类型。
3. 写 `SSIENR.SSIC_EN = 0`，关闭控制器。
4. 配置 `IMR` 并读 `ICR` 清旧中断状态；`ICR` 是 read-to-clear 寄存器。这里不等待 `intr`，也不轮询 `ISR.DONES`。
5. 写 `SER.SER = 0`，释放所有片选。
6. 通过大写 REG/FIELD 句柄配置 `CTRLR0`、`SPI_CTRLR0`、`CTRLR1`、`BAUDR`、FIFO threshold、DMA threshold、DMA 寄存器和 `RX_SAMPLE_DELAY`。
7. 写 `SSIENR.SSIC_EN = 1` 使能控制器。
8. 返回时仍保持 `SER.SER = 0`。真正选中片选由 `sequence/operation/transfer` 在 PIO 预填 FIFO 或 DMA 启动边界完成。

真正的 transfer completion 等待发生在 `sequence/operation/transfer`，位于寄存器配置、片选激活、PIO/DMA 启动之后。

## Chip Select Helpers

| Task | 用途 |
| --- | --- |
| `select_hardware_chip()` | 写 `SER.SER = cfg.ser`，在 transaction 边界选中硬件片选。 |
| `release_hardware_chip_selects()` | 写 `SER.SER = 0`，在 transaction 完成后释放所有硬件片选。 |

core 只执行寄存器动作，不判断本次是硬件 CS 还是软件 CS。软件 CS callback 的调用顺序由 transfer sequence 编排。

## Completion Helpers

| Task | 用途 |
| --- | --- |
| `wait_idle()` | 轮询 `SR.TFE && !SR.BUSY`，用于 PIO、外部 DMA fallback，或无完成中断的内置 DMA fallback。 |
| `check_internal_dma_dones()` | 读取 `ISR.DONES`，只用于内置 DMA top `intr` 触发后的完成确认。 |

core 不决定 completion mode，也不判断本次是否 DMA；这些决策在 sequence 层完成。非 DMA PIO 不调用 `check_internal_dma_dones()`。

## Register Access Rules

- 不保存寄存器地址，不维护字符串到寄存器的映射。
- task 内先写 `rm = settings.regmodel`，再使用 `rm.<REG>.read(status, data)`、`rm.<REG>.<FIELD>.set(...)`、`rm.<REG>.write(status, rm.<REG>.get())`。
- RAL `read()` / `write()` 的 `status` 只作为 API 形参保留，不逐次检查 `UVM_IS_OK`。
- 不使用 `update()`。
- 不封装 `set_field/get_field/update_reg` 这类二次寄存器 API。
- core 工具类不是 `uvm_component` 时，通过调用方注入 `uvm_report_object report_context`，并用它的 `uvm_report_enabled()` / `uvm_report_info()` 控制 `UVM_LOW` 与 `UVM_DEBUG` 打印。

## DR Helpers

PIO 写 DR 使用 `write_items_to_dr()`。flash operation sequence 负责构造 DR item stream：standard 模式逐 byte 放入 opcode/address/dummy；enhanced 模式把 opcode 和完整 address 各打包成一个 32-bit control item，再追加 payload data items。core 不理解各 item 的协议语义，只负责等待 `SR.TFNF` 并逐 item 写 `DR`。

PIO 读 payload 使用 `read_dr_to_payload()`。它按 payload length 等待 `SR.RFNE`，逐 byte 读 `DR`，并把实际读回数据写入 generic payload。

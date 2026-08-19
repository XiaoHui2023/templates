# Chip Select Control

DW SPI 模板显式区分两种片选控制模式。

| 模式 | 枚举 | 默认 | 行为 |
| --- | --- | --- | --- |
| 硬件 CS | `HARDWARE_CS` | 是 | controller 通过 `SER.SER` 选择片选，sequence 不调用片选 callback。 |
| 软件 CS | `SOFTWARE_CS` | 否 | sequence 在 primitive transfer 边界调用 `activate_chip_select()` / `release_chip_select()` callback，同时仍写 `SER.SER` 让控制器内部传输启动。 |

`settings.default_cs_control_mode` 是全局默认值，默认 `HARDWARE_CS`。`transfer_configuration.cs_control_mode` 是单次传输配置，可显式覆盖。

## 支持矩阵

| 速度/模式 | 硬件 CS | 软件 CS | 原因 |
| --- | --- | --- | --- |
| 1x | 支持 | 支持 | 1x 固定为标准单线 SPI，软件在 primitive transfer 边界拉低/释放 CS 可以表达外设模型行为。 |
| 2x enhanced | 支持 | 不支持 | 双线增强模式对 command/address/data phase 连续性更敏感，软件 callback 无法保证 SCLK 级边界。 |
| 4x enhanced | 支持 | 不支持 | 四线增强模式同上，必须使用控制器硬件 CS。 |

约束规则：

- `SOFTWARE_CS` 只允许 `host_mode == MASTER`。
- `SOFTWARE_CS` 只允许 `speed_multiplier == 1`。
- 1x 自动使用 standard；2x/4x 自动使用 enhanced，用户不单独配置 frame mode。
- 2x/4x 只使用 `HARDWARE_CS`。

## Transaction 边界

SPI flash 的 CS window 由协议操作决定：

- command-only 操作独立占用一个 CS window，例如 `WREN 0x06`、`RDSR 0x05`、`CHIP_ERASE 0xC7`。
- status-register write 也独立占用一个 CS window，例如 P25Q21L QPP 前的 `WRSR 0x01 + 0x00 + 0x02`。
- read 这类多阶段操作必须把 opcode、address、dummy、data 放在同一个 CS window 内；program/write 必须把 opcode、address、data 放在同一个 CS window 内，写流程不插入 dummy clock。
- `WREN 0x06` 与后续 page program 必须是两个 CS window：先发 `0x06` 并释放 CS，再发 program opcode + address + data。QPP 还需要在 `WRSR` 后再次 `WREN`，因为 WRSR 会清除 WEL。

DW SPI 的 native CS 有一个关键行为：`SER` 置位后传输可以自动开始；如果 TX FIFO 在一个 memory operation 中途变空，硬件 CS 可能提前释放，导致 flash 操作被截断。因此硬件 CS + PIO 必须先尽量预填 FIFO，并在 CS 有效期间及时补写 `DR0`，保证 FIFO 不被喂空。

flash write 的非 DMA PIO flow 不按 FIFO 容量拆成多个 program transaction。正确边界是 `WREN` 一个 CS window，随后整个 `program opcode + address + data` 一个 CS window；CPU/PIO 只是按 FIFO 状态慢慢补 `DR0`。当前模板用 `SR.TFNF` 轮询补 FIFO；后续可以升级为 TX FIFO threshold interrupt/refill 状态机。

## SER 与 Callback

即使选择 `SOFTWARE_CS`，模板仍然按 `cs_id` 写 `SER.SER`。这里的 `SER` 用于控制器内部传输选择和使能；软件 CS 表示外部片选行为由 callback 注入。

顺序：

1. 配置寄存器并保持 `SER.SER = 0`。
2. PIO 预填 DR0 或 DMA 准备完成。
3. `SOFTWARE_CS` 时先调用 `activate_chip_select(cs_id)`。
4. 写 `SER.SER = cfg.ser` 启动/选择控制器内部传输。
5. 完成传输并等待 idle 或 DMA done。
6. 写 `SER.SER = 0`。
7. `SOFTWARE_CS` 时调用 `release_chip_select(cs_id)`。

## Callback Override

`dw_spi_callback` 的默认 `activate_chip_select()` / `release_chip_select()` 会 `uvm_fatal`，用于要求软件 CS 场景必须 override。

```systemverilog
class my_spi_cb extends dw_spi_callback;
    `uvm_object_utils(my_spi_cb)

    virtual task activate_chip_select(int cs_id);
        // drive external CS active
    endtask

    virtual task release_chip_select(int cs_id);
        // drive external CS inactive
    endtask
endclass
```

UVM callback 列表为空时，callback 宏不会调用 base callback。因此使用 `SOFTWARE_CS` 时，环境必须注册一个 callback 实现类。

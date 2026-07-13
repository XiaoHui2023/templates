# Chip Select Control

DW SPI 模板显式区分两种片选控制模式：

| 模式 | 枚举 | 默认 | 行为 |
| --- | --- | --- | --- |
| 硬件 CS | `HARDWARE_CS` | 是 | 由控制器 `SER.SER` 选择片选，sequence 不调用片选 callback。 |
| 软件 CS | `SOFTWARE_CS` | 否 | sequence 在 primitive transfer 前后调用 `activate_chip_select()` / `release_chip_select()` callback。 |

`settings.default_cs_control_mode` 是全局默认值，默认 `HARDWARE_CS`。`transfer_configuration.cs_control_mode` 是单次传输配置，随机约束会优先 soft 跟随 `settings.default_cs_control_mode`，也允许用户显式覆盖。

## 支持矩阵

| 速度/模式 | 硬件 CS | 软件 CS | 原因 |
| --- | --- | --- | --- |
| 1x standard | 支持 | 支持 | 标准 SPI 单线时序简单，软件在 transfer 边界拉低/释放 CS 足够表达大多数外设模型。 |
| 1x enhanced | 支持 | 不支持 | enhanced 使用 `SPI_CTRLR0` 的 instruction/address/dummy/data 分阶段时序，CS 边界应由控制器保持。 |
| 2x enhanced | 支持 | 不支持 | 双线增强模式对 command/address/data phase 的连续性更敏感，软件 callback 无法保证 SCLK 级精确边界。 |
| 4x enhanced | 支持 | 不支持 | 四线增强模式同上，必须使用控制器硬件 CS。 |

约束规则：

- `SOFTWARE_CS` 只允许 `host_mode == MASTER`。
- `SOFTWARE_CS` 只允许 `frame_mode == STANDARD`。
- `SOFTWARE_CS` 只允许 `speed_multiplier == 1`。
- 2x/4x 必然是 enhanced，因此只能使用 `HARDWARE_CS`。

## SER 与 Callback

即使选择 `SOFTWARE_CS`，模板仍然按 `cs_id` 配置 `SER.SER`。这里的 `SER` 用于控制器内部传输选择和使能；软件 CS 表示外部片选行为由 callback 注入。

如果集成环境需要完全屏蔽控制器 CS pad，应在顶层连线、pad mux、interface 或 callback 环境中处理。模板不假设不存在的“关闭硬件 CS pad”寄存器位。

## Callback Override

`dw_spi_callback` 的默认 `activate_chip_select()` / `release_chip_select()` 会 `uvm_fatal`，用于要求软件 CS 场景必须 override：

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


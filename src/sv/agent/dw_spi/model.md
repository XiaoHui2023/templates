# model

`model` 目录只放数据类型定义，不放执行逻辑。

## `settings.sv`

`settings` 是 sequencer 持有的运行期配置对象。

主要内容：

- generated capability：最大 lane、最大倍速、是否支持 master/slave、standard/enhanced、general/flash SPI。
- runtime default：默认 SPI mode、默认 CS、默认地址字节数、默认 BAUDR、FIFO threshold、rx sample delay。
- shared handle：`regmodel`、`vif`。

sequence 通过 `p_sequencer.settings` 读取这些信息。寄存器访问使用 `settings.regmodel.<reg>.write/read`。

## `configuration.sv`

`configuration` 是单次寄存器配置包。

它只保存本次需要写入的寄存器值，例如：

- `ctrlr0`
- `ctrlr1`
- `ssienr_disable`
- `ssienr_enable`
- `ser`
- `baudr`
- `txftlr`
- `rxftlr`
- `imr`
- `dmacr`
- `dmatdlr`
- `dmardlr`
- `rx_sample_dly`
- `write_rx_sample_dly`

它可以引用 `settings` 做约束，计算默认分频、FIFO threshold、DMA threshold、rx sample delay 等值。

`configuration` 不放寄存器地址。寄存器地址由 regmodel 托管，operation/core 只通过明确的 `settings.regmodel.<reg>` 访问寄存器。

## `dw_registers.md`

`dw_registers.md` 记录 DesignWare SPI/SSI 寄存器字段语义，给代码和 review 提供参考。

它可以记录寄存器名、field、效果、频率关系和状态位含义；但生成代码不能从 `configuration` 中取地址常量。需要实际读写时通过 regmodel 访问。

## 相关执行逻辑

重复的寄存器 pack/apply 逻辑放在 `core/register_access.sv`。

`register_access` 是实例化工具类。sequence 创建对象后注入 `p_sequencer.settings`，再调用实例方法。不要把 core 做成 static 函数集合。

具体操作入口在 sequence：

- `sequence/operation/init_registers`
- `sequence/operation/transfer`

`sequencer` 只保存基础句柄和 callback wrapper。`kit_sequencer` 只做快捷启动封装。

# SRAM Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | 写入和读取起始地址，默认 0 |
| `sram_size` | 控制器 SRAM 容量，必填 test 输入，不从配置读取 |
| `block_size` | 单块大小；eMMC/SDIO 默认 512，SDCard 默认 2048 |
| `data_width` | 传输位宽，默认 `settings.boot_cfg.default_data_width`，即最大位宽 |
| `bus_speed_mode` | 传输速度模式，默认 `settings.boot_cfg.default_bus_speed_mode`，即默认最高速 |
| `dma_enable` / `dma_sel` | 数据搬运方式 |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 调用 `switch_bus_seq` 切到 `bus_speed_mode` 和 `data_width`；默认是最高速和最大位宽。
3. 正常写入 `sram_size + block_size` 字节，更新 scoreboard expected memory。
4. blocked read `sram_size` 字节；等全部 buffer ready 后再读寄存器，结果按 scoreboard 正常比较。
5. blocked read `sram_size + block_size` 字节；等全部 buffer ready 后再读寄存器。
6. 第二遍不按普通 memory 比较；检查第一块等于溢出的最后一块，说明 SRAM 中原第一块已被覆盖。

## 关键点

- 该测试验证控制器 SRAM 暂存和覆盖行为，不是普通 card memory 读写一致性测试。
- 测试自身负责切换到最高速和最大位宽；调用前不需要额外 `switch_bus`。
- 第一遍读满 `sram_size`，数据仍按地址与 scoreboard expected memory 比较。
- 第二遍多读一个 block，只检查 SRAM 覆盖特征，不调用普通 scoreboard 比较。
- `sram_size` 是必填 test 输入参数；不要放回 `boot_cfg`。
- 通过 kit sequencer 调用时用 `sram_test(.sram_size(...), .block_size(...))`；直接启动 `sram_test_seq` 时需先置 `has_sram_size = 1` 并约束 `sram_size`。

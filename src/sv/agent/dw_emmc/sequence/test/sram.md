# SRAM Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | 写入和读取起始地址，默认 0 |
| `sram_size` | 控制器 SRAM 容量，作为 test 输入，不从配置读取；默认 4096 |
| `block_size` | 单块大小；eMMC/SDIO 默认 512，SDCard 默认 2048 |
| `dma_enable` / `dma_sel` | 数据搬运方式 |

## 流程

1. 未初始化时运行 `initial_seq`。
2. 正常写入 `sram_size + block_size` 字节，更新 scoreboard expected memory。
3. blocked read `sram_size` 字节；等全部 buffer ready 后再读寄存器，结果按 scoreboard 正常比较。
4. blocked read `sram_size + block_size` 字节；等全部 buffer ready 后再读寄存器。
5. 第二遍不按普通 memory 比较；检查第一块等于溢出的最后一块，说明 SRAM 中原第一块已被覆盖。

该测试会先写入足够数据，不依赖外部初始镜像。

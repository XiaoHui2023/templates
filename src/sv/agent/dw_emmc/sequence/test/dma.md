# DMA Test

通过 DMA 执行读写测试，默认写 1 块再读 1 块。

## 输入

| 字段 | 作用 |
| --- | --- |
| `addr` | 读写命令参数来源 |
| `count` | 读写块数 |
| `write_enable` / `read_enable` | 是否执行写、读 |

## 流程

1. 约束 `dma_enable == 1`。
2. 执行 `rw_test_seq`。
3. 写路径完成后更新 scoreboard expected memory。
4. 读路径完成后按 `should_compare` 比较。

## 设计

### mobile_storage

SDIO 使用 IDMAC 描述符链表，不使用 SD ADMA2 描述符格式，也不使用 `dma_sel` 写寄存器。`CTRL_R.USE_INTERNAL_DMAC` 选择 internal DMAC，`DBADDR_R` 写 `idmac_descriptor.descriptor_addr`，数据地址写在 DES2，`BMOD_R.SWR` 复位 IDMAC，`BMOD_R.DE` 开启 IDMAC，`PLDMND_R` 写 `32'h1` 触发 DMA。

单块 512B 写传输默认描述符：DES0 为 `32'h8000_000c`，DES1 为 `32'h0000_0200`，DES2 为数据 buffer 地址，DES3 为下一描述符地址。

### 比较

只写或只读默认不比较；同时写读时比较。

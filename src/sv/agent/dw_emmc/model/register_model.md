# Register Model

## 产品

| `controller_ip` | 寄存器模型 | 说明 |
| --- | --- | --- |
| `mshc` | `DWC_mshc` | 默认值，保持原模板行为 |
| `mobile_storage` | `DWC_mobile_storage` | 生成 legacy mobile storage 寄存器访问 |

## 差异

| 行为 | `mshc` | `mobile_storage` |
| --- | --- | --- |
| 卡时钟使能 | `CLK_CTRL_R.INTERNAL_CLK_EN`、`CLK_CTRL_R.SD_CLK_EN` | `CLKENA_R.CCLK_ENABLE[0]` |
| PLL | `CLK_CTRL_R.PLL_ENABLE` | 无 |
| 分频选择 | `CLK_CTRL_R.UPPER_FREQ_SEL`、`CLK_CTRL_R.FREQ_SEL` | `CLKDIV_R.CLK_DIV[9:0]` |
| 分频算法选择 | `CLK_CTRL_R.CLK_GEN_SELECT` | 无 |
| 内部时钟稳定 | `CLK_CTRL_R.INTERNAL_CLK_STABLE` | 无 |
| VDD1 电源 | `PWR_CTRL_R.SD_BUS_PWR_VDD1` | `PWREN_R.CARD_PWR_EN[0]` |
| VDD1 电压 | `PWR_CTRL_R.SD_BUS_VOL_VDD1` | 无 |
| VDD2 电源 | `PWR_CTRL_R.SD_BUS_PWR_VDD2` | 无 |
| VDD2 电压 | `PWR_CTRL_R.SD_BUS_VOL_VDD2` | 无 |
| 命令 inhibit | `PSTATE_REG.CMD_INHIBIT` | 无 |
| 数据 inhibit | `PSTATE_REG.CMD_INHIBIT_DAT` | `STATUS_R[9] == 0` |
| 插卡 | `PSTATE_REG.CARD_INSERTED == 1` | `CARD_DETECT_R.CARD_DETECT[0] == 0` |
| 卡稳定 | `PSTATE_REG.CARD_STABLE` | 无 |
| 数据活跃 | `PSTATE_REG.DAT_LINE_ACTIVE`、`RD_XFER_ACTIVE`、`WR_XFER_ACTIVE` | `STATUS_R[9] == 0` |
| DMA 地址 | `SDMASA_R` / `ADMA_SA_LOW_R` | IDMAC 区域，当前写 `DBADDR_R` |
| 块大小 | `BLOCKSIZE_R.XFER_BLOCK_SIZE` | `BLKSIZ_R.BLK_SIZE` |
| 块数量 | `BLOCKCOUNT_R.BLOCK_CNT` | `BYTCNT_R.BYTE_CNT`，按 `block_size * block_count` 写字节数 |
| 命令参数 | `ARGUMENT_R.ARGUMENT` | `CMDARG_R.CMD_ARG` |
| 传输模式 | `XFER_MODE_R` | 合并到 `CMD_R` |
| 数据宽度 | `HOST_CTRL1_R.DAT_XFER_WIDTH` / `EXT_DAT_XFER` | `CTYPE_R.CARD_WIDTH` |
| 高速模式 | `HOST_CTRL1_R.HIGH_SPEED_EN`、`HOST_CTRL2_R.UHS_MODE_SEL`、`HOST_CTRL2_R.SIGNALING_EN` | `UHS_REG_R` |
| DMA 选择 | `HOST_CTRL1_R.DMA_SEL` | `CNTRL_R.user_internal_dmac`，RO，硬件固定 |
| Host 控制 | `HOST_CTRL1_R`、`HOST_CTRL2_R` 其他字段 | 无 |
| 普通中断状态 | `NORMAL_INT_STAT_R` | `MASKED_INTS_R` + `RAW_INTS_R` |
| 错误中断状态 | `ERROR_INT_STAT_R` | `MASKED_INTS_R` + `RAW_INTS_R` |
| 中断使能 | `NORMAL_INT_STAT_EN_R`、`ERROR_INT_STAT_EN_R`、`NORMAL_INT_SIGNAL_EN_R`、`ERROR_INT_SIGNAL_EN_R` | `INTMSK_R` |
| 响应寄存器 | `RESP01_R`、`RESP23_R`、`RESP45_R`、`RESP67_R` | `RESP0_R`、`RESP1_R`、`RESP2_R`、`RESP3_R` |
| 软件复位 | `SW_RST_R` | 无 |
| 块间隔控制 | `BGAP_CTRL_R` | 无 |
| 唤醒控制 | `WUP_CTRL_R` | 无 |
| 超时控制 | `TOUT_CTRL_R` | `TMOUT_R`，4-bit 变 32-bit |
| PIO 数据口 | `BUF_DATA_R` | 无，数据传输必须用 DMA |
| 自动命令状态 | `AUTO_CMD_STAT_R` | 无 |

## 生成规则

- `controller_ip` 默认是 `mshc`。
- `class_regmodel`、`class_regmodel_rm`、`class_regmodel_rm_vd1` 默认是空字符串。
- 类名为空时，RAL 顶层类名、寄存器块类名、寄存器块 member 名都按 `controller_ip` 生成。
- 类名非空时，使用用户指定值。
- 不存在的 mobile storage 字段不生成访问代码。
- `freq_sel` 在 `mshc` 下拆成 `[9:8]` 和 `[7:0]`，在 `mobile_storage` 下整体写入 `CLKDIV_R.CLK_DIV[9:0]`。
- `mobile_storage` 自动启用 `enable_dma`；显式配置 `enable_dma: false` 会报错。
- `mobile_storage` 的 tuning 寄存器映射未确认前，`tune_en` 会直接 fatal。

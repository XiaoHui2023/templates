---
name: dw_emmc_notes
description: dw_emmc 模板族：当前有效的 DesignWare eMMC/SD/SDIO 生成规则与维护要求。
---

# dw_emmc 设计笔记

> 变更记录见 `dw_emmc_changelog`；矛盾以最新条目为准。

## controller_ip

- `controller_ip` 选择 `mshc` 或 `mobile_storage`。
- 默认保持 `mshc`。
- `mshc` eMMC initial flow 的 CMD1 OCR 默认使用 `32'h00ff8080`，请求 byte access；不要回退到 `32'h40ff8080` 的 sector access。
- 新增寄存器差异时，在最小 operation 层做条件展开，不复制整棵模板目录。

## mobile_storage

- 当前模板库暂时只支持 `controller_ip: mobile_storage` + `card_type: sdio`。
- 用户说 `mobile_storage` 时，默认就是 SDIO 场景；不要用 mobile_storage eMMC 生成物代表用户问题。
- `mshc` 保持原有 eMMC/SDCard/SDIO 逻辑，不因 mobile_storage 修复而改变旧流程。
- power up 写 `CLKDIV_R`、`CLKENA_R` 后，通过 `CMD_R.UPDATE_CLOCK_REGISTERS_ONLY` 加载 CIU 时钟参数。
- access 发普通命令前必须清 `CMD_R.UPDATE_CLOCK_REGISTERS_ONLY`。
- access 写 `CMD_R.START_CMD` 前全清 `RINTSTS_R` 并配置 `INTMASK_R`；等待阶段先读取 `MINTSTS_R`，消费已经置位的中断，不在等待入口再次清状态。
- DMA 模式使用 IDMAC 描述符链表，`DBADDR_R` 写描述符地址，`PLDMND_R` 写 `32'h1` 触发。
- 数据命令不反向强制打开 DMA；SDIO CMD53 允许 `data_present_sel == 1` 且 `dma_enable == 0`。
- mobile_storage 没有 RAL `BUF_DATA_R`；非 DMA SDIO 通过 `default_map.get_base_addr() + 0x200` FIFO 窗口前门 CPU 访问。
- mobile_storage 非 DMA SDIO 写数据要在命令发出前预装 FIFO，不能等 `CMD_COMPLETE` 后才 PIO 搬数据。
- mobile_storage 读数据命令前开启读 FIFO 保护：`CARDTHRCTL_R.CARD_RD_THR_EN = 1`，`CARD_RD_THRESHOLD = xfer_block_size`，`FIFOTH_R.RX_WMARK = xfer_block_size / 2`。
- mobile_storage 不强制启用 DMA；生成 DMA 时，kit `rw_test()` 默认 `use_dma = 0`，需要 DMA 时显式打开。

## 验收

- 改 `.sv.j2` 后渲染 eMMC、SDCard、SDIO 默认配置。
- mobile_storage 相关修改要渲染 `controller_ip: mobile_storage`、`card_type: sdio` 且 `enable_dma: true`。
- 检查生成物空行、保留字、参数方向和未展开 Jinja 标记。

## mobile_storage FIFO read

- `RXDR` 只作为块级唤醒。
- 非 DMA 读 FIFO 时，每个 word 前读 `STATUS_R`，确认 `STATUS_R[2] == 0` 后再读 FIFO 窗口。
- 轮询期间检查 `RINTSTS_R[11]`，出现 FIFO 下溢或上溢时 fatal。
- `STATUS_R[29:17]` 只作为调试参考，不能替代 FIFO 空标志。

---
name: dw_emmc_changelog
description: dw_emmc 模板族：按时间记录 DesignWare eMMC/SD/SDIO 生成规则与修复决议。
---

# dw_emmc 变更记录

## 2026-08-24

- `cpu_read` / `cpu_write` callback 默认实现改为 `uvm_fatal`，避免未重载时静默失败。
- mobile_storage SDIO 非 DMA CMD53 数据传输改为通过 `default_map.get_base_addr() + 0x200` FIFO 窗口前门 CPU 读写；MSHC `BUF_DATA_R` 路径保持不变。
- 纠正族级记录中的旧口径：mobile_storage 不强制启用 DMA，kit `rw_test()` 的 `use_dma` 默认仍为 0。

## 2026-08-20

- mobile_storage SDIO 命令完成等待改为状态优先：access 写 `CMD_R.START_CMD` 前清 CMD complete 并配置 `INTMASK_R`；`wait_interrupt` 先消费已置位 `MINTSTS_R`，不再入口全清 `RINTSTS_R`；`check_error` 轮询降噪。
- mobile_storage 生成 DMA 时，kit `rw_test()` 默认 `use_dma = 1`，避免默认走不存在的 PIO 数据口；mshc 默认仍为 0。
- 修正 `command_request` 和 `access_request` 的 DMA 约束方向：保留 `dma_enable -> data_present_sel`，删除 `data_present_sel -> dma_enable`，允许 SDIO CMD53 非 DMA 数据传输；`mshc` 旧流程不改变。
- 明确当前模板库的 mobile_storage 暂时只支持 SDIO：用户说 `mobile_storage` 时按 `controller_ip: mobile_storage` + `card_type: sdio` 验证；`mshc` 维持原有 eMMC/SDCard/SDIO 行为。

## 2026-08-19

- mobile_storage 的 `check_error` 只清 `RINTSTS_R` 错误位，普通中断位由 `wait_interrupt` 独占清除。
- mobile_storage 在 power_up 和 access 配置 `CTRL_R.INT_ENABLE`，保证 `INTMASK_R` 前还有全局中断使能。

## 2026-08-18

- mobile_storage access 写普通 `CMD_R` 前清 `UPDATE_CLOCK_REGISTERS_ONLY`，避免 power up 的 update-clock-only 状态残留到 CMD5 等普通命令。
- mobile_storage 数据宽度字段改为 `CTYPE_R.CARD_WIDTH`，不使用 `CARD_WIDTH0`。
- mobile_storage 修正 command response 检查位约束：R4 不检查 CRC/index，NR 不检查 CRC/index，R6/R7 纳入 CRC/index 检查；非 mobile_storage 保持原有映射。
- mobile_storage 删除 SDIO initial 中因 CMD5 假错误遗留的 CMD3 前命令软复位；非 mobile_storage 保持原流程。
- 修正 `cpu_config_response` 成员声明位置，避免生成物保留字检查误判 `bit`。
- 收紧 `agent`、`kit_sequencer`、`check_clock_frequence_test_seq`、`boot_initiation_command_request` 的模板空行。
- 建立 dw_emmc 族级 notes/changelog，用于记录 controller_ip 差异与验收规则。

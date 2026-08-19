---
name: dw_emmc_changelog
description: dw_emmc 模板族：按时间记录 DesignWare eMMC/SD/SDIO 生成规则与修复决议。
---

# dw_emmc 变更记录

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

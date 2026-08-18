# dw_emmc mobile_storage 命令流程修复

- status: done
- created: 2026-08-18 09:19 +08:00
- updated: 2026-08-18 11:02 +08:00
- scene: dw_emmc mobile_storage 命令流程修复

## 记录

- 用户反馈 mobile_storage power up 后 `CMD_R.UPDATE_CLOCK_REGISTERS_ONLY` 保持为 1，access 阶段 CMD5 被 RTL 当作 update clock only。
- access 操作在写普通 `CMD_R` 前清 `UPDATE_CLOCK_REGISTERS_ONLY`。
- 寄存器差异文档、sequence 总结、power up 文档和用户根 designware eMMC skill 同步维护。
- 渲染检查暴露既有空行和 `bit` 误判问题，已作为同轮模板门禁修复纳入。
- 四种配置已完成一次渲染：默认 eMMC、mobile_storage、sdcard、sdio。
- 后续检查发现 SDCard/SDIO 的生成文件仍有连续空行，继续收紧对应模板。
- 已收紧 ACMD 基类和 SDIO CMD53 模板空行；保留字检查、参数方向检查通过。
- 连续空行扫描、五件套检查和 `git diff --cached --check` 通过。

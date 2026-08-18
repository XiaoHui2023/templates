---
name: project-design-notes
description: templates 仓库标准五件套入口：Agent 当前有效的设计意图与硬性要求。
---

# 设计笔记（当前有效）

> 变更记录见 `.cursor/skills/project-changelog/SKILL.md`；矛盾以 changelog 最新条目为准。

## 设计意图

- templates 仓库保留既有模板族专档，标准五件套用于项目门禁与跨族协作。
- `src/sv/agent/<族>/` 的持续性要求写入族级 `.cursor/skills/<族>_notes/SKILL.md`。
- `dw_spi` DMA 写使用低字节 `SPIDR.SPI_INST`；DMA 读在选择 CS 前预填 TX FIFO，并达到 `TXFTLR+1` 启动门槛。

## 硬性要求

- 实质性修改前读取项目预加载入口、设计笔记、changelog、目标与工作记录。
- 修改 `src/sv/**/*.sv.j2` 后运行该族 `jinja_build`，并检查生成物空行、保留字和参数方向。
- 当轮产生可提交改动时，完成质量门禁后提交并推送到远程。

## 备忘与待定

- templates 专用入口仍由 `.cursor/skills/templates-preload-skills/SKILL.md` 维护。

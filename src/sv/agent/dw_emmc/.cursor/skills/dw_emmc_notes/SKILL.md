---
name: dw_emmc_notes
description: dw_emmc 模板族：当前有效的 DesignWare eMMC/SD/SDIO 生成规则与维护要求。
---

# dw_emmc 设计笔记

> 变更记录见 `dw_emmc_changelog`；矛盾以最新条目为准。

## controller_ip

- `controller_ip` 选择 `mshc` 或 `mobile_storage`。
- 默认保持 `mshc`。
- 新增寄存器差异时，在最小 operation 层做条件展开，不复制整棵模板目录。

## mobile_storage

- power up 写 `CLKDIV_R`、`CLKENA_R` 后，通过 `CMD_R.UPDATE_CLOCK_REGISTERS_ONLY` 加载 CIU 时钟参数。
- access 发普通命令前必须清 `CMD_R.UPDATE_CLOCK_REGISTERS_ONLY`。
- 数据传输使用 IDMAC 描述符链表，`DBADDR_R` 写描述符地址，`PLDMND_R` 写 `32'h1` 触发。

## 验收

- 改 `.sv.j2` 后渲染 eMMC、SDCard、SDIO 默认配置。
- mobile_storage 相关修改要渲染 `controller_ip: mobile_storage` 且 `enable_dma: true`。
- 检查生成物空行、保留字、参数方向和未展开 Jinja 标记。

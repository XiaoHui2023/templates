# Reg Test

## 输入

无独立输入字段。测试依赖 `settings.boot_cfg` 中的初始化配置。

## 流程

1. 创建 `initial_seq`。
2. 在 `pre_switch_yield` 期间读取 CSD/CID。
3. 在 `post_switch_yield` 期间读取 eMMC EXT_CSD，或 SD SCR。
4. 恢复 yield，让初始化流程继续。

该测试用于确认初始化窗口内的寄存器类命令可用，不重复封装单个 op 或 flow。

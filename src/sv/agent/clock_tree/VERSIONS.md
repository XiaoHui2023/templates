# 时钟树版本

## v1 基线

- 基线提交：`9166cab3`
- 输入：`settings` 与 `nodes`。
- 代码：`model/` 与 `core/`。

## v2 节点插件化

- 输入：保留 v1；JSON 也可将节点直接放在根对象，`settings` 为保留键。
- 代码：`node/base/` 提供通用节点和配置 API，`node/plugin/` 提供节点类型，`node/config/` 提供配置入口。
- 配置：节点以 hook 声明配置阶段、测量、flip、route 与 PLL lock 行为；`config_reg_core` 实现通用配置 API。
- 轻量配置：`config.f` 只引入节点、寄存器配置和 `config_reg` 入口。

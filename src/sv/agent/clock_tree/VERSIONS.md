# 时钟树版本

## v6 分组输入与共享输出

- 输入：根对象使用 settings 和 nodes，nodes 可从独立文件导入；不再接受扁平节点输入。
- 节点排除：exclude 默认为 false，为 true 时不生成节点，与时钟 enabled 分开。
- stable：省略 enabled 时补 1，显式关闭时报错。
- 插件：增加 clk_div_with_clken，三个输出共用分频状态和配置。

## v1 基线

- 基线提交：`9166cab3`
- 输入：`settings` 与 `nodes`。
- 代码：`model/` 与 `core/`。

## v2 节点插件化

- 输入：保留 v1；JSON 也可将节点直接放在根对象，`settings` 为保留键。
- 代码：`node/base/` 提供通用节点和配置 API，`node/plugin/` 提供节点类型。
- 配置：节点以 hook 声明配置优先级、配置动作与完成等待；`tree.configure` 统一调度，具体 sequence 自行选择测量、flip、route 的对象。
- 轻量配置：`config.f` 只引入节点、寄存器配置和 `tree.configure` / `config_reg` 入口。

## v3 单一输入协议

- 输入：根对象只保留 `settings`；其余根键直接定义节点，`nodes` 包装不再支持。
- 内部：`Models.nodes` 和 `Tree.nodes` 仅作为已校验的运行时索引，不是输入字段。
- 目标：新增节点只扩展节点 schema 与对应插件，不增加输入层分支。

## v4 tree 配置门面

- 配置：`tree.configure` 是唯一实现入口；`config_reg(tree)` 与 kit 的 `config_reg` 只委托给它。
- 低功耗：`tree.configure(.low_power(1))` 先改变时钟求解偏好，再走完整配置。
- 边界：删除配置 operation；`config.f` 不加载 `top/`、`component/` 或 `sequence/`。

## v5 显式插件注册

- 输入：所有 `present` 节点都生成 SV 类型与实例；未知 `kind` 不由 Python 过滤。
- 插件：`node/plugin/` 只放扩展类实现；`all.f` 与 `config.f` 显式列出要编译的插件，不扫描目录自动注册。
- 诊断：缺少对应 SV 类或遗漏 filelist 条目时，由最终 SV 编译直接报错。

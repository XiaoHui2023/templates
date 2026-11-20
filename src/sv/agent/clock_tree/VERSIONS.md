# 时钟树版本

## v6 当前设计

- 输入：根对象使用 settings 和 nodes，nodes 可从独立文件导入；不再接受扁平节点输入。
- 节点排除：exclude 默认为 false，为 true 时不生成节点，与时钟 enabled 分开。
- 插件属性：与公共字段平级，不再使用 config 容器；output_config 保留按输出组覆盖。
- stable：省略 enabled 时补 1，显式关闭时报错。
- 插件：增加 clk_div_with_clken，三个输出共用分频状态和配置。
- 配置：插件声明动作、依赖和共享临时使用，取消数值优先级。
- 低功耗：独立调用 `tree.low_power()`，再手动设置所需时钟，最后调用无参数 `tree.configure()`；替代 v4 的合并参数。
- 日志：统一使用 UVM verbosity，不再提供日志控制布尔参数。

## 历史设计

以下记录旧接口，不表示当前仍然支持。

| 版本 | 当时设计 | 后续变化 |
| --- | --- | --- |
| v1 | 基线提交 `9166cab3`；settings 与 nodes，逻辑分布于 model、core | 节点逻辑迁入插件 |
| v2 | 引入 node/base、node/plugin，允许根对象直接定义节点 | v6 统一为 nodes 字段 |
| v3 | 只接受扁平节点输入 | v6 恢复 settings、nodes 分组 |
| v4 | tree.configure 统一配置，low_power 曾作为参数 | v6 改为独立调用 low_power |
| v5 | 显式登记 SV 插件，未知类型由最终编译检查 | 保留显式清单；节点排除字段改为 exclude |

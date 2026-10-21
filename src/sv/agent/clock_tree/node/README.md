# 节点契约

每个插件只扩展 `node_base`；tree、component 和 operation 只保存 `node_base` 句柄，不识别具体节点类型。

| 契约 | 基类 hook | 插件职责 |
| --- | --- | --- |
| 拓扑 | `set_source`、`collect_source_nodes`、`collect_input_keys_from_source` | 声明上游与输入端口键 |
| 配置 | `configuration_priority`、`requires_observed_descendant`、`apply_configuration`、`await_configuration`、`post_register_bind`、`collect_control_regs` | 定义配置顺序、寄存器动作与完成条件 |
| 观测 | `is_observable`、`supports_duty_observation`、`is_stability_anchor` | 声明可测端点、占空比与稳定性能力 |
| 低功耗 | `apply_low_power_preference` | 写入节点自己的低功耗偏好 |
| 功能 | `has_functional_contract`、`run_functional_contract` | 在自身端口上激励、写自身寄存器并验证输出 |
| 原生输入 | `preserves_native_input` | 标明功能检查不能驱动的输入 |

`tree.configure()` 只排序并调用配置契约。`check_measure` 只按观测契约筛选；`flip_check` 只按功能契约调用；`route_check` 只按拓扑边遍历。新增节点仅添加插件文件并登记到 `node/plugin.f`，不修改 Python、tree 或 operation。

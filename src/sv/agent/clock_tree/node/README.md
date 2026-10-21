# 节点契约

每个节点插件只扩展 `node_base`，tree 和 operation 始终保存 `node_base` 句柄。

| 契约 | 基类 hook | 插件职责 |
| --- | --- | --- |
| 拓扑 | `collect_source_nodes`、`collect_input_keys_from_source` | 声明上游和输入端口键 |
| 配置 | `configuration_priority`、`configuration_stage`、`configure_stage`、`wait_for_lock` | 定义写入顺序、寄存器动作和完成条件 |
| 观测 | `is_measure_selected`、`check_measure_duty` | 声明能否被 measure 请求选中及占空比能力 |
| 状态变换 | `has_transition_check`、`run_transition_check` | 在自身端口上激励、写本节点寄存器并验证输出 |
| 原生输入 | `uses_native_transition_input` | 标明 transition 时不能 force 的 RTL 时钟源 |

`tree.configure()` 只排序并调用配置 hook。`check_measure` 按观测契约选择节点；`flip_check` 按 transition hook 调用节点；`route_check` 只按拓扑契约遍历边。新增 SV 节点时，注册其插件文件并按需要覆盖这些 hook，不修改 tree 或 operation。

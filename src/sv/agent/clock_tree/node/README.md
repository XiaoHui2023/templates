# 节点

`tree.nodes` 是 `node_base` 句柄队列，包含全部节点实例。多输出节点的每个输出组各占一项。

## 控制

| 成员 | 默认值 | 作用 |
| --- | --- | --- |
| `_should_print` | `0` | 打印解析结果、固定约束和分组等诊断字段 |
| `_should_check` | `1` | 允许 measure、flip 和 route 检查该节点 |

`_should_print` 不隐藏节点对象或普通字段，也不控制检查日志。`_should_check` 不改变连接、约束或寄存器配置；route 的任一端关闭检查时，该连线跳过。

```systemverilog
foreach (tree.nodes[i]) begin
    tree.nodes[i]._should_print = 1;
end
tree.clk_cpu._should_check = 0;
```

## 配置钩子

| 钩子 | 插件提供的行为 |
| --- | --- |
| `post_register_bind` | 寄存器绑定完成后的初始化 |
| `set_output_peer` | 连接同一物理器件的其它输出实例 |
| `configuration_priority` | 配置优先级，负数表示不参与，数值小的优先 |
| `requires_observed_descendant` | 是否要求下游存在可测量节点 |
| `apply_configuration` | 写入本节点寄存器，并返回 `configured` |
| `waits_after_configuration` | 是否需要配置完成等待 |
| `await_configuration` | 等待锁定等完成条件 |
| `apply_low_power_preference` | 设置本节点的低功耗偏好 |
| `collect_control_regs` | 返回控制寄存器，用于识别共享字段 |

`tree.configure` 的执行顺序：

1. 检查 build 状态，按参数应用低功耗偏好，然后随机化。
2. 筛选配置优先级非负且满足下游要求的节点。
3. 按优先级升序调用 `apply_configuration`；同优先级保持队列顺序。
4. 对 `configured` 为真且声明需要等待的节点调用 `await_configuration`。

寄存器编码、读回比较和重复配置判断由插件实现。

## 测量钩子

| 钩子或成员 | 用途 |
| --- | --- |
| `is_observable` | 是否提供可测量端点 |
| `supports_duty_observation` | 是否检查占空比 |
| `vif` | 测量接口 |
| `_resolved_active` | 期望有无时钟 |
| `_resolved_freq` | 期望频率，单位 Hz |

`check_measure` 遍历 `tree.nodes`，按检查请求、`_should_check`、接口和测量能力选择节点。活动检查通过后，按请求检查频率；请求与节点均允许时检查占空比。节点共用接口时共用测量状态。

## 功能钩子

| 钩子 | 用途 |
| --- | --- |
| `has_functional_contract` | 是否提供功能检查 |
| `run_functional_contract` | 施加激励、配置寄存器、检查输出并释放驱动 |
| `is_stability_anchor` | 是否需要保护该节点及其上游 |
| `preserves_native_input` | 是否保留原生输入时钟 |

`flip_check` 串行调用选中节点的 `run_functional_contract`，传入提供寄存器访问和测量服务的 `node_test_api`。插件返回 `did_check`、`did_skip` 和失败数；前两个结果必须恰有一个为真。

## 连线钩子

| 钩子 | 用途 |
| --- | --- |
| `set_source` | 绑定上游节点与输入键 |
| `collect_source_nodes` | 返回全部上游节点 |
| `collect_input_keys_from_source` | 返回连接指定上游的输入键 |
| `get_in_vif`、`get_out_vif` | 返回指定端口的 virtual interface |
| `interfaces_connected` | 全部接口绑定后的初始化 |

`route_check` 通过拓扑钩子找出前级输出和后级输入，逐个前级驱动 0、1 并检查全部下游输入，然后释放驱动。它使用前级默认输出 `get_out_vif()`；多输入由输入键区分。

## 扩展

1. 添加 `node/python/plugins/<kind>.py`，声明节点 `config` 和可选全局设置。
2. 在 `node/python/registry.py` 登记 Python 插件与设置。
3. 添加 `node/plugin/<kind>.sv.j2`，实现字段、约束和需要的钩子，并加入 `node/plugin.f.j2`。

`config` 由 Python 插件校验，`output_config` 覆盖单个输出组。未知 `kind` 仍生成对应 SV 类型，缺少实现时由 SV 编译报错。

Python 插件可重载 `normalize_outputs` 提供固定输出组，重载 `port_paths_for_output` 分配每组端口；公共层不判断具体节点类型。

通用 tree 和 sequence 通过 `node_base` 调用虚方法；节点专属逻辑写在对应插件，可复用的能力写在 support 基类。

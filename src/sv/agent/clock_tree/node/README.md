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
| `has_configuration` | 是否提供最终配置动作 |
| `requires_observed_descendant` | 是否要求下游存在可测量节点 |
| `apply_configuration` | 写入本节点寄存器，并返回 `configured` |
| `await_configuration` | 等待锁定等完成条件 |
| `clock_rate_hz` | 临时开启后按实际配置编码计算频率，单位 Hz |
| `observe_configuration` | 读取规划所需的实际状态 |
| `plan_configuration` | 声明最终动作的依赖 |
| `plan_requirement` | 声明满足外部临时需求的依赖 |
| `acquire_requirement`、`release_requirement` | 建立和释放临时状态 |
| `execute_configuration` | 执行插件内部动作 token，默认 0 为最终配置 |
| `configuration_owner`、`availability_key` | 标识多输出或别名共享的控制资源 |
| `configuration_signature` | 比较共用控制标识的最终编码 |
| `configuration_preserves_availability` | 最终状态是否允许临时使用 |
| `apply_low_power_preference` | 设置本节点的低功耗偏好 |
| `collect_control_regs` | 返回控制寄存器，用于识别共享字段 |

`tree.configure` 的执行顺序：

1. 检查 build 状态，按参数应用低功耗偏好，然后随机化。
2. 登记提供配置且满足下游要求的节点，读取实际状态。
3. 插件声明动作与临时需求，公共上下文合并共享使用并检查整个依赖图。
4. 确认无环后串行执行；每个动作返回时已完成自身等待。

寄存器编码、读回比较和重复配置判断由插件实现。

单独编译 `config.f` 时，clock 和 cell 仍作为下游端点参与配置筛选，不要求 interface。加载测量接口后，端点仍按实际接口连接判断。

### 无毛刺切换

1. mux 读回旧 sel；与目标相同则跳过写入和等待。
2. 声明旧、新输入需要保持运行，直到切换等待完成。
3. 输入提供者声明自己的准备动作；两端就绪后，等一个最慢输入周期，再写 sel。
4. 等待 `switch_cycles` 个最慢输入周期，之后才释放输入使用。
5. 共享输入等全部使用结束后，再应用关闭目标；没有最终目标的临时 gate 恢复读回值。

mux 只描述切换需求，不判断上游类型。gate 和 PLL 通过同样的临时使用钩子提供运行状态；公共配置代码只管理动作、依赖及共享使用。具体结构见[配置计划](base/config/README.md)。

频率由源、分频比和 DTO 步进编码计算，不使用已关闭 gate 的零频率，也不使用约束容差带中的随机值。PLL 临时供钟复用自身编程和锁定逻辑，使用结束后应用最终电源目标；寄存器绑定不全或无法确认锁定时，拒绝供钟要求。

`switch_cycles` 是目标 IP 的切换时间预算，不是硬件完成状态。没有完成状态寄存器时，须按同步级数和 IP 时序设置，不能靠延长等待修复已停止的输入。

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

1. 添加 `node/python/plugins/<kind>.py`，继承 `NodePluginConfig`，声明节点属性、校验规则和可选全局设置。
2. 在 `node/python/registry.py` 登记 Python 插件与设置。
3. 添加 `node/plugin/<kind>.sv.j2`，实现字段、约束和需要的钩子，并加入 `node/plugin.f.j2`。

节点输入中，插件属性与公共字段平级。基础模型处理连接、路径和寄存器声明，其余属性交给对应 Python 插件校验；公共模型不声明具体插件属性。`output_config` 与节点属性合并后，由同一插件校验每个输出组。

Python 插件不能声明与公共字段、只读属性或方法同名的字段。已注册插件拒绝未知属性；未知 `kind` 保留合法的标量属性并生成对应 SV 类型，缺少实现时由 SV 编译报错。

```python
from pydantic import Field

from ..config import NodePluginConfig


class CustomConfig(NodePluginConfig):
    """自定义节点属性。"""

    ratio: int | None = Field(default=None, ge=1, description="输入与输出的分频比")
```

```yaml
nodes:
  custom0:
    kind: custom
    source: osc
    ratio: 4
```

新增属性只修改该 Python 插件；`sv_assignments` 默认将显式填写的属性转换为 SV 成员赋值。需要改变名字、编码或默认行为时，在插件中重载该方法。

Python 插件可重载 `normalize_outputs` 提供固定输出组，重载 `port_paths_for_output` 分配每组端口；公共层不判断具体节点类型。

存在可共享的配置字段时，重载 `register_encoding`，根据 role 和实例访问表达式返回实际写入的 SV 编码表达式。表达式应直接使用随机成员和整数运算，不调用有副作用或依赖寄存器读回的函数；reset、load 等非稳态字段返回 None。

公共层按寄存器字段和比特范围分组，将每组其它编码约束为与第一项相等。不同分频插件按编码比较，不假定分频比相同。共享组中只要有节点声明了编码，其余节点也必须提供编码，否则输入报错。

通用 tree 和 sequence 通过 `node_base` 调用虚方法；节点专属逻辑写在对应插件，可复用的能力写在 support 基类。

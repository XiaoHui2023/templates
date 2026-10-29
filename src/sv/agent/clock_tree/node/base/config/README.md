# 配置计划

## 结构

| 文件 | 职责 |
| --- | --- |
| `action.sv` | 动作所有者、插件内部 token、依赖和后继 |
| `lease.sv` | 提供者、就绪、释放和插件自己的临时快照 |
| `context.sv` | 实际状态、共享使用、完整验环及串行执行 |

`node_base` 提供规划和执行钩子，`config_reg_core` 收集插件计划。核心不识别具体节点类型，也不解释寄存器编码。

`tree.low_power()` 只设置偏好；用户随后修改节点目标，再调用 `tree.configure()` 随机化并应用配置。规划不会重新覆盖用户设置。

## 对象与数据

所有类名带 `class_prefix`。以下省略前缀。

| 对象 | 成员 | 含义 |
| --- | --- | --- |
| `config_action` | `id`、`owner`、`token`、`label` | 计划内编号、执行节点、插件内部动作编号和诊断名称 |
| `config_action` | `action_kind` | `EXECUTE` 调用插件动作，`ACQUIRE` 建立可用状态，`RELEASE` 结束临时使用 |
| `config_action` | `prerequisites[$]`、`followers[$]` | 前置动作和后继动作的整数 ID，不互相持有动作句柄 |
| `config_action` | `lease_key` | 取得/释放动作对应的共享记录标识 |
| `config_action` | `deferred`、`next_poll_ns` | 是否分次检查完成条件，以及下一次可检查的绝对纳秒时刻 |
| `config_lease` | `provider`、`ready`、`release_action` | 实际提供者、就绪动作和释放动作 |
| `config_lease` | `state` | 插件自己的 `uvm_object` 临时快照，核心不解释内容 |
| `config_lease` | `has_target` | 此资源是否已有最终配置负责，不应再恢复临时快照 |
| `config_context` | `actions[$]`、`targets[int]` | 全部动作，以及按节点实例 ID 索引的最终动作 |
| `config_context` | `leases[string]` | 按物理可用控制 key 合并的共享记录 |
| `config_context` | `planned_providers[string]` | 同一 key 下已贡献依赖的逻辑提供者，避免递归重复规划 |
| `config_context` | `observations[int]` | 按节点实例 ID 保存本次读回状态 |
| `config_context` | `runtime_states[int]` | 插件执行状态，例如编程结束后确定的锁定截止时间；与规划读回分开保存 |
| `config_context` | `sealed`、`failed`、`io` | 计划是否封存、是否失败、寄存器服务 |

每次配置创建新上下文，不跨配置保存临时快照，也不修改节点的 `_resolved_*` 作为临时状态。

## 请求接口

目前资源请求只有一种：**提供者保持可用，直到指定动作完成**。频率和开关通过节点最终目标表达；复位、load、选路等属于插件动作，不是额外的公共请求类型。

| 接口 | 调用者与作用 |
| --- | --- |
| `context.require_available(provider, completion)` | 消费者请求提供者可用，返回共享 `config_lease` |
| `node.require_source(context, completion)` | 单输入插件请求自身 source，并将 completion 排在上游就绪之后 |
| `context.add_action(owner, token, label)` | 插件添加动作；token 0 为最终目标，其余由插件自己定义 |
| `context.after_action(action, prerequisite)` | 声明 action 必须等待 prerequisite 完成；重复边只登记一次 |
| `context.defer_action(action)` | 将本计划的 EXECUTE 动作改为分次完成检查，仍遵守原依赖 |
| `context.target(node)` | 查找节点的最终动作，没有参与配置则返回 null |
| `context.set_observation(node, state)`、`observation(node)` | 保存与读取插件规划需要的实际状态 |
| `context.set_runtime_state(node, state)`、`runtime_state(node)` | 保存与读取插件在执行时建立的状态，不修改已封存的依赖图 |
| `context.fail(message)`、`has_failed()` | 报告并传播失败；fatal 不作为语言异常使用 |

`require_available` 只建立共享记录和依赖，**不会立即打开时钟**。调用者仍须把自己的使用动作排在返回的 `lease.ready` 之后；它只自动保证 release 在 completion 之后。

## 节点钩子

| 钩子 | 职责与默认行为 |
| --- | --- |
| `has_configuration()` | 是否登记最终动作；默认否 |
| `requires_observed_descendant()` | 是否要求有效下游观测端点；默认否 |
| `configuration_owner()` | 多输出对应的实际控制者；默认自身 |
| `availability_key()` | 等价取得/释放操作的共享 key；默认节点实例 ID |
| `configuration_signature()` | 同一 key 的最终编码签名；默认空，不允许多个目标靠空签名宣称一致 |
| `configuration_preserves_availability()` | 最终目标是否保持可用；默认是 |
| `observe_configuration(context)` | 读取规划所需状态；默认空操作 |
| `plan_configuration(context, target)` | 为最终目标补动作与依赖；默认空操作 |
| `plan_requirement(context, lease)` | 补上游需求；默认保持 source 可用至自身 release，并让自身 ready 等待上游 ready |
| `acquire_requirement(context, lease)` | 建立临时状态；默认空操作 |
| `release_requirement(context, lease)` | 结束临时使用；默认空操作 |
| `execute_configuration(context, token)` | 默认仅接受 token 0，调用 apply；实际配置后调用 await |
| `poll_configuration(context, token, complete, retry_ns)` | 只检查一次完成条件；未完成时返回下次检查间隔，默认拒绝未实现的检查 |
| `apply_configuration(io, configured)` | 节点寄存器配置；默认返回未配置 |
| `await_configuration(io)` | 配置完成等待；默认空操作 |

默认的透明传播不等于所有节点都能供钟。可控提供者必须自行校验寄存器、输入、锁状态及其它必要条件，并实现取得/释放行为。

## 执行

1. 保留随机化得到的最终状态，登记每个参与节点的目标动作。
2. 调用 `observe_configuration`，读取插件规划需要的实际状态。
3. 调用 `plan_configuration`，添加动作及依赖。token 由插件自己解释，0 表示目标动作。
4. `require_available(provider, completion)` 声明提供者必须保持可用，直到指定动作完成。
5. 提供者通过 `plan_requirement` 声明上游要求；上下文合并共享使用，并安排就绪、释放和目标动作。
6. 完整拓扑检查通过后，由单执行器运行就绪动作和分次完成检查。循环依赖在任何动作执行前报错。

动作通过 `context.io` 访问寄存器。不依赖其它节点的数值优先级；需要长时间等待的插件拆成启动与完成动作，完成前不放行后继。

### 等待调度

1. 先执行当前全部就绪的普通动作；遇到 deferred 动作时放入待检查队列。
2. 对到达 `next_poll_ns` 的动作调用一次 `poll_configuration`。完成才递减后继依赖，否则按正数 `retry_ns` 安排下一次检查。
3. 检查完成若产生新的就绪动作，先执行新动作，不等待其它无关器件。
4. 没有可运行工作时才等待最近的下一次检查时刻；不逐纳秒空转。

寄存器访问始终串行。普通动作仍是原子 task，不在访问途中取消线程。插件的 poll 可以读状态寄存器，但不能在内部持续轮询或长时间 sleep；总线访问本身的超时由寄存器服务负责。

### PLL 启动与锁定

1. 开启目标拆为 program 与 lock-completion。program 等参考输入就绪；completion 等 program；下游等 completion。
2. program 复用原寄存器匹配与编程函数。返回时记录绝对截止时间，之后每次 lock 检查共享这个截止，不因排队或重试而延长。
3. 独立 PLL 先分别编程，硬件同时锁定；某个 PLL 提前就绪，它的下游可以先继续。级联 PLL 仍需等参考 PLL 就绪。
4. 最终关闭但被临时使用的 PLL 同样拆为临时 program 与 lock-completion。确认锁定后才宣布 lease.ready；所有使用完成后再执行关闭目标。
5. 即使配置匹配而没有写寄存器，仍确认 lock。超过截止后的读回不作为按时锁定的证据。

各 PLL 的具体编码函数不变；配置计划不识别 PLL 类名。锁轮询间隔最多 2us，最后一次检查受剩余预算限制。

### 一次请求的展开

1. 消费者先取得自己的 completion 动作，再调用 `require_available(provider, completion)`。
2. 上下文调用 `configuration_owner()` 与 `availability_key()`，查找已有共享记录。
3. 首次使用该 key 时，创建 lease、ACQUIRE 和 RELEASE，添加 RELEASE 等待 ACQUIRE 的依赖。
4. 每个不同逻辑提供者调用一次 `plan_requirement()`。即使共用 key，各入口自己的上游依赖也不能省略。
5. 添加 RELEASE 等待 completion 的依赖，将这次使用并入共享生命周期。
6. 消费者把实际使用动作排在 lease.ready 之后。提供者的上游请求按同一机制展开。
7. 全部插件规划完后，上下文检查共享目标：保持可用的最终目标在 ACQUIRE 前执行；破坏可用的目标在 RELEASE 后执行。
8. 完整拓扑排序通过后才执行。ACQUIRE 调用取得钩子，EXECUTE 调用动作钩子，RELEASE 调用释放钩子。

共享记录不靠“最后一个线程”的计数判断结束，而是让同一个 RELEASE 依赖全部消费者的 completion。当前串行执行，没有请求线程或后台 worker。

### mux 切换示例

1. mux 观察旧选择；与目标相同则不添加切换动作。
2. 创建 select 动作，并请求旧、新输入保持可用至 mux 的 target 完成。
3. select 等待两个输入 ready；target 等待 select。gate 等提供者再声明自己的上游需求。
4. 提供者建立可用状态，mux 预等一个最慢输入周期，然后 select 写入选择值。
5. select 写入完成后，为 target 设置 `switch_cycles` 个最慢输入周期的完成时刻。target 到时完成，其间可执行其它器件的动作，之后才允许两个输入 RELEASE。
6. 旧 gate 的最终关闭动作等待 RELEASE；新 gate 的最终开启动作保持有效。其它消费者仍使用旧 gate 时，关闭继续等待。

配置需求与 sequence 的 `req` 不同。measure 使用观测能力，flip 使用节点功能契约，route 使用端口拓扑；它们只在最初配置阶段间接使用此计划，不把测量和 force 转成 availability 请求。

## 插件

普通插件保留 `apply_configuration` 与可选 `await_configuration`，默认目标动作调用它们。需要多步动作时，重载 `plan_configuration` 和 `execute_configuration`，使用插件内部的 token 区分动作。

提供者在 `acquire_requirement` 建立可用状态，在 `release_requirement` 结束临时使用。快照放在 `lease.state`，读回状态放在上下文；不修改 `_resolved_*`，也不为中间状态重新随机化。

`configuration_preserves_availability` 为真时，目标动作先于就绪；为假时，目标动作等待全部使用结束。释放不是关闭：最终目标为开启时保持开启，没有目标时才恢复快照。

## 共享与失败

多输出通过 `configuration_owner` 返回实际控制者。等价控制别名可返回相同的 `availability_key`，共用一次取得和释放；每个逻辑提供者仍声明自己的上游依赖。

共用控制标识的最终动作必须给出相同的 `configuration_signature`。签名由插件按实际目标编码生成；缺失或冲突时，计划在写入前失败，不按先后顺序覆盖。

`tree.build` 登记寄存器控制切片。上下文将重叠控制的目标写入安排在使用之前或之后；编码是否兼容由原有约束和插件校验，不由调度器猜测。

完整拓扑预检与依赖释放为 O(V+E)；共享控制检查另按使用记录与目标节点比较，待完成动作按轮询批次检查。硬件等待可以重叠，但 task 和寄存器访问仍由一个执行器串行调用，不添加总线锁或工作线程。

规划错误直接终止，尚未执行的动作不会写入硬件。执行期间超时不继续释放尚未确认的资源，也不承诺任意硬件动作都能回滚。周期等待只是插件的时间预算；存在完成状态时，应由插件检查该状态。

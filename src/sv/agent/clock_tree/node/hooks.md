# 节点钩子

通用代码通过 node_base 调用虚方法。没有实现的可选能力使用默认行为；插件只重载自己需要的部分。

## Python 属性

| 方法 | 输入与结果 |
| --- | --- |
| `binding_assignments(registers)` | 校验当前输出组的寄存器，返回额外SV成员赋值 |
| `sv_assignments()` | 返回显式属性对应的SV成员赋值 |
| `normalize_outputs(outputs)` | 校验或补充输出组 |
| `port_paths_for_output(output, ports)` | 为当前输出组分配输入、输出和测量端口 |
| `register_encoding(role, access)` | 返回稳态控制编码表达式；reset、load等触发字段返回None |

新增全局设置时继承 NodePluginSettings，向 `PLUGIN_SETTINGS` 登记作用域。模板通过 `plugin_value` 读取回退值；十进制容差用 `plugin_fraction` 转成整数分子、分母。

共享寄存器比较的是最终写入编码，不是节点的分频比。表达式直接使用随机成员和整数运算，不能调用寄存器读回或有副作用的函数。

## 连接与初始化

| 方法 | 默认行为或用途 |
| --- | --- |
| `set_source(key, parent)`、`get_source(key)` | 空键使用source，其他键使用sources数组 |
| `set_output_peer(key, peer)` | 保存同器件输出对象 |
| `collect_source_nodes(nodes)` | 收集上游节点 |
| `collect_input_keys_from_source(parent, keys)` | 找出连接某上游的输入键 |
| `post_register_bind()` | 绑定完成后的初始化，默认无操作 |
| `interfaces_connected()` | 所有接口分配后的初始化，默认无操作 |
| `get_in_vif(key)`、`get_out_vif(key)` | 返回指定端口的virtual interface |

接口声明及相关方法放在接口保护宏内。纯配置编译时不能引用未编译的 interface。

## 配置

| 方法 | 默认行为或用途 |
| --- | --- |
| `has_configuration()` | 默认false，不添加最终配置动作 |
| `requires_observed_descendant()` | 默认false；可要求存在有效下游测量节点 |
| `configuration_owner()` | 默认自身；多输出可返回共同控制者 |
| `availability_key()` | 默认节点实例ID；等价控制可共用key |
| `configuration_signature()` | 最终编码签名，默认空 |
| `configuration_preserves_availability()` | 默认true，最终状态仍可供使用 |
| `observe_configuration(context)` | 读取规划所需状态，默认无操作 |
| `plan_configuration(context, target)` | 增加最终动作依赖，默认无操作 |
| `plan_requirement(context, lease)` | 默认请求上游运行到自身release |
| `acquire_requirement(context, lease)` | 建立临时状态，默认无操作 |
| `release_requirement(context, lease)` | 恢复临时状态，默认无操作 |
| `execute_configuration(context, token)` | 默认token 0执行apply；实际配置后调用await |
| `apply_configuration(cfg, configured)` | 默认不写寄存器，返回未配置 |
| `await_configuration(cfg)` | 默认无等待 |
| `poll_configuration(context, token, complete, retry_ns)` | 分次检查完成；未实现时拒绝调用 |
| `clock_rate_hz()` | 根据实际编码计算频率，默认沿source读取 |
| `default_output_activity(upstream)` | 返回输出活动预期，或指定继承预期的输入；默认 `auto` |
| `collect_control_regs(regs)` | 返回已登记控制切片 |
| `apply_low_power_preference()` | 默认不改变状态 |

共享key的多个最终目标要有相同且非空的编码签名。临时供钟放在lease，不修改 `_resolved_*`。完整机制见 [配置计划](base/config/README.md)。

## 测量

| 方法 | 默认行为或用途 |
| --- | --- |
| `is_observable()` | vif已连接时为true |
| `supports_duty_observation()` | 默认false，普通测量不检查占空比 |
| `output_duty_check_enabled(key)` | 默认true，功能输出检查占空比 |
| `output_frequency_window(key)` | 自身输出的平均周期数，默认1 |
| `measurement_frequency_window(key)` | 合并自身与前级的平均窗口 |
| `output_max_rise_gap_ns(expected, input_hz, key)` | 最大上升沿间隔，单位ns；input_hz为0时使用树中配置 |

普通测量沿连接计算窗口；flip 使用独立输入，只采用节点自身窗口。量化输出应提供实际激励频率。增大平均窗口不改变最终允许误差。

## 功能检查

`run_functional_contract` 是公共执行入口，插件不重载它。它保存实际控制切片，调用插件检查，恢复配置，最后释放驱动。

| 方法 | 插件职责 |
| --- | --- |
| `has_functional_contract()` | 默认false；声明是否提供功能检查 |
| `exercise_functional_contract(api, did_check, did_skip, failures)` | 驱动输入、操作寄存器、检查输出；返回时保留驱动 |
| `restore_configuration(cfg, saved)` | 默认恢复控制切片；延迟提交器件要补load、复位或等待 |
| `is_stability_anchor()` | 默认false；stable节点作为保护起点 |
| `preserves_native_input()` | 默认false；时钟源可声明保留原生输入 |

插件用 `prepare_functional_clock(api, upstream, key, stimulus_hz, input_hz)` 准备输入。受保护的输入只测量，其他输入可驱动；返回的频率用于计算输出期望。公共入口只释放本次启动的驱动。

`did_check` 与 `did_skip` 必须恰有一个为true。缺接口或输入准备失败时，在写寄存器前返回skip。写过寄存器后返回did_check，公共入口恢复控制切片。仿真终止或总线致命错误不保证恢复。

插件通过 `check_output(api, vif, label, expected, passed, key, input_hz)` 检查输出；key与input_hz可省略。测量和寄存器访问使用传入服务，不在公共sequence里添加器件类型判断。

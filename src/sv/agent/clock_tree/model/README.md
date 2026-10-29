# 时钟树模型

类型名带 `class_prefix` 前缀。

## tree

| 成员 | 类型 | 含义 |
| --- | --- | --- |
| `nodes` | `node_base` 队列 | 全部节点实例，每个输出组各占一项 |
| `built` | `bit` | build 已完成 |
| `<节点名>` | 对应插件类型 | 单输出节点句柄 |
| `<节点名>[string]` | 对应插件类型的关联数组 | 多输出节点，按输出组名索引 |

| 方法 | 作用 |
| --- | --- |
| `build(regmodel)` | 绑定寄存器，调用节点初始化钩子，随机化；成功后置位 built |
| `low_power()` | 向所有节点设置低功耗偏好，不写寄存器 |
| `configure()` | 按当前请求重新随机化并配置寄存器 |
| `require_built(ctx)` | 未 build 时终止并打印调用位置 |

`config_reg(tree)` 是 `tree.configure()` 的全局 task 入口，不是 sequence。配置需要在 task 上下文调用。

## 公共成员

| 成员 | 类型 | 含义 |
| --- | --- | --- |
| `kind` | `string` | 插件名 |
| `source` | `node_base` | 默认输入的前级 |
| `sources[string]` | `node_base` 关联数组 | 具名输入的前级 |
| `output_name` | `string` | 当前输出组名，单输出时为空 |
| `output_peers[string]` | `node_base` 关联数组 | 同一物理器件的全部输出实例 |
| `_should_print` | `bit` | 打印诊断字段，默认 0 |
| `_should_check` | `bit` | 允许检查，默认 1 |
| `_resolved_freq` | `rand longint` | 解析后的频率，单位 Hz |
| `_resolved_active` | `rand bit` | 解析后的活动状态 |

基类约束频率大于 0 当且仅当节点活跃；连接了默认前级时，默认继承前级频率和活动状态。插件可重载这些约束。

接口已编译时，节点还提供 `vif`、`in_vif`、`out_vif` 以及具名端口数组 `in_vifs[string]`、`out_vifs[string]`。未编译接口时，这些成员和依赖它们的钩子不参与编译。

## 插件属性

寄存器绑定和配置动作由各插件负责。

| 插件 | 属性 | 作用 |
| --- | --- | --- |
| `source`、`source_pad` | `frequence` | 固定输出频率 |
| `clk` | `frequence`、`enabled` | 指定频率和开关，默认均为 -1，不主动固定 |
| `clk` | `low_power` | 软约束关闭偏好，默认 0 |
| `clk` | `stable`、`check_duty` | 稳定保护、占空比检查，默认分别为 0、1 |
| `clk` | `unfix_frequence`、`unfix_enabled` | 忽略显式频率或开关要求，默认 0 |
| `cell` | `frequence`、`enabled` | 可选频率和开关，默认均为 -1；检查活动和频率，不测占空比 |
| `cell` | `cell_kind` | cell 名字 |
| `pll_tci`、`pll_sc`、`pll_dw`、`pll_inno` | `frequence`、`enabled` | 目标频率和开关；enabled 为 -1 时跟随前级活动状态，无前级时开启 |
| `pll_inno` | `group_id` | 共用 PLL 系数的输出组名 |
| `gate` | `open`、`unfix_open`、`fix_open`、`fix_close` | 开关要求及固定控制 |
| `mux` | `sel`、`unfix_sel`、`max_sel`、`switch_cycles`、`switch_timeout_ns` | 选择要求、范围及切换等待预算 |
| `div_div`、`div_div_r`、`div_dto` | `ratio`、`unfix_ratio` | 分频比要求及固定控制 |
| `div_div` | `max_ratio` | 分频比上限，构造默认 64 |
| `clk_div_with_clken` | `ratio`、`unfix_ratio` | 三输出共用的分频要求，合法值为 2、3、4、6 |
| `inv`、`inv_cell`、`inv_mux` | `inverted`、`fix_inverted` | 反相状态及固定控制 |

gate、mux 和分频器随机化的是 `_resolved_open`、`_resolved_sel`、`_resolved_ratio`，不是 `open`、`sel`、`ratio`。反相器的 `inverted` 本身为 rand。

clk 显式填写正频率且未填写 enabled 时默认开启；显式 enabled 优先。enabled 大于 0 且未解除频率要求时使用指定频率；enabled 为 0 时可保留 frequence 供下次开启。stable 强制开启。低功耗只改变软偏好，不覆盖显式开关，也不清除频率要求。

输入 stable 为 true 且省略 enabled 时，插件初始化 enabled 为 1；显式冲突在输入阶段报错。

## 寄存器绑定

| 成员 | 类型 | 含义 |
| --- | --- | --- |
| `field` | `uvm_reg_field` | 寄存器模型字段句柄 |
| `offset` | `int unsigned` | 切片起始位 |
| `width` | `int unsigned` | 切片位宽 |
| `alias_count` | `int unsigned` | 同一绑定的使用数 |
| `has_read` | `bit` | 已执行总线读取 |

`is_bound()` 判断 field 是否连接。寄存器访问按切片合并值，保留其它位；批量修改同一个父寄存器时只写回一次。

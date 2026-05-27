# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**callback** 注册、**trees** 访问、配置与行为便捷方法均在此句柄上 |
| **config_db** | 键 **`trees`**，值为 **base_tree** 队列；环境在例化 **agent** 前设置 |

环境先由 **connection** 建好各 **tree** 并 **randomize**，再通过 **config_db** 提供给 **agent** 后例化 **agent**。

## sequencer

基础 **sequencer**；**callback** 注册于此类型；**sequence** 的 **`p_sequencer`** 仅声明为此类型。

| 成员 | 说明 |
| --- | --- |
| `trees` | 已绑定的 **base_tree** 队列；每棵 **tree** 自带 **settings** |

| 方法 | 说明 |
| --- | --- |
| `configure_settings` | 对给定 **settings** 实例触发 **on_configure_settings**；仅声明 **setting_defs** 时存在 |

## kit_sequencer

派生 **sequencer**；**agent.sqr** 的实际类型。配置与 **sequence/behavior** 的便捷入口均在本类。

| 方法 | 说明 |
| --- | --- |
| `configure_tree` | 对单棵 **tree** 的 **settings** 调用 **configure_settings**；仅声明 **setting_defs** 时存在 |
| `configure_all_trees` | 对 **trees** 队列中每棵 **tree** 依次配置；仅声明 **setting_defs** 时存在 |
| `run_enable_clock_source` | 入参单个 **node_base**；填 **enable_clock_source** 的 **req** 并 **start**，返回 **rsp** |
| `run_enable_clock_source_nodes` | 入参 **node_base** 队列；对每个节点调用上一方法 |
| `run_enable_clock_source_tree` | 入参 **base_tree**；对其中全部 **source** 节点依次调用上一方法 |

## sequence · behavior

每种行为独占 **`sequence/behavior/<行为名>/`**，含 **req**、**rsp** 两个 **uvm_sequence_item** 与 **behavior** 序列。**behavior** 为 **`uvm_sequence#(REQ,RSP)`**，由 **kit_sequencer** 填入 **req** 后 **start**，再取 **rsp**。全仓约定见用户根 **`systemverilog-uvm-sequence-behavior`**。

| 行为目录 | 说明 |
| --- | --- |
| `enable_clock_source` | 按节点 **frequence** 打开对应 **vif** 时钟发生开关 |

## sequence · base

**base_seq** 的 **`p_sequencer`** 类型为 **sequencer**，不引用 **kit_sequencer**，以便 **sequence** 层只依赖基础 **sequencer** 的公开成员与方法。

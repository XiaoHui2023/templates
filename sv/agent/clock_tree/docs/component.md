# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**callback** 注册、**trees** 访问、配置便捷方法均在此句柄上 |
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

派生 **sequencer**；**agent.sqr** 的实际类型。使用者与 **sequence** 以外的测试代码通过 **`agent.sqr`** 调用本类便捷方法。

| 方法 | 说明 |
| --- | --- |
| `configure_tree` | 对单棵 **tree** 的 **settings** 调用 **configure_settings** |
| `configure_all_trees` | 对 **trees** 队列中每棵 **tree** 依次配置 |

## sequence · base

**base_seq** 的 **`p_sequencer`** 类型为 **sequencer**，不引用 **kit_sequencer**，以便 **sequence** 层只依赖基础 **sequencer** 的公开成员与方法。

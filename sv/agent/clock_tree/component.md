# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**callback** 注册、**trees** 访问、配置与行为便捷方法均在此句柄上 |
| **config_db** | 键 **`trees`**，值为 **base_tree** 队列；环境在例化 **agent** 前设置 |

环境先由 **connection** 建好各 **tree** 并 **randomize**，再通过 **config_db** 提供给 **agent** 后例化 **agent**。**agent** 将 **trees** 赋给 **sqr.trees**，不向基础 **sequencer** 传递。

## sequencer

基础 **sequencer**；**callback** 注册于此类型；**sequence** 的 **`p_sequencer`** 仅声明为此类型。不持有 **trees**，不从 **config_db** 读取 **trees**。

| 方法 | 说明 |
| --- | --- |
| `configure_settings` | 对给定 **settings** 实例触发 **on_configure_settings**；仅声明 **setting_defs** 时存在 |

## kit_sequencer

派生 **sequencer**；**agent.sqr** 的实际类型。持有 **trees[$]**；配置与 **sequence/behavior** 的便捷入口均在本类。

| 成员 | 说明 |
| --- | --- |
| `trees` | **base_tree** 队列，由 **agent.build_phase** 赋值 |

| 方法 | 说明 |
| --- | --- |
| `configure_tree` | 对单棵 **tree** 的 **settings** 调用 **configure_settings**；仅声明 **setting_defs** 时存在 |
| `configure_all_trees` | 对 **trees** 队列中每棵 **tree** 依次配置；仅声明 **setting_defs** 时存在 |
| `run_set_clock_gen` | 入参 **node**、**gen_en** 默认 1；启动 **set_clock_gen** 行为 |
| `run_set_clock_gen_nodes` | 入参节点队列与 **gen_en**；逐节点调用上一方法 |
| `run_set_clock_gen_tree` | 入参 **tree** 与 **gen_en**；对该树全部带 **vif** 的节点调用 |
| `run_set_clock_gen_trees` | 入参 **trees** 队列与 **gen_en**；对每棵树调用上一方法 |
| `gen_source_clock` | 无参；对 **trees** 中全部 **source** 节点执行 **set_clock_gen(1)** |
| `run_set_pll` | 入参 **pll** 节点；启动 **set_pll**，寄存器细节待补 |
| `run_apply` | 入参 **tree**；启动 **apply**，**gate/div/dto/mux** 寄存器待补 |
| `run_check_clk` | 入参 **tree**；检查全部 **clk** 节点频率 |
| `run_check_pll` | 入参 **tree**；检查全部 **pll** 节点频率 |
| `run_check_duty` | 入参 **tree**、**gen_after_check** 默认 0；检查占空比，可选检查后对该节点 **set_clock_gen(1)** |

## sequence · behavior

每种行为独占 **`sequence/behavior/<行为名>/`**，含 **req**、**rsp** 与 **behavior** 序列。**behavior** 的 **`p_sequencer`** 类型为 **sequencer**，不得引用 **kit_sequencer** 或调用 kit 便捷方法。测试平台经 **kit** 填 **req** 后 **start** 行为。

| 行为目录 | 说明 |
| --- | --- |
| `set_clock_gen` | 按 **req.gen_en** 与节点 **frequence** 设置 **vif** 时钟发生；**gen_en** 为 0 关闭 |
| `set_pll` | **pll** 频率与寄存器配置，主体待补 |
| `apply` | 应用 **gate**、**div**、**dto**、**mux** 配置寄存器，主体待补 |
| `check_clk` | 检查 **tree** 内全部 **clk** 频率 |
| `check_pll` | 检查 **tree** 内全部 **pll** 频率 |
| `check_duty` | 检查带 **vif** 节点占空比；**req.gen_after_check** 为真且 **frequence** 大于 0 时对该节点打开 **set_clock_gen** |

## sequence · base

**base_seq** 派生 **spec**，类型实参为 **uvm_sequence**。**base_seq** 的 **`p_sequencer`** 类型为 **sequencer**。

## tree 外部约束

每棵 **{name}_tree** 声明 **cst_base**、**cst_user**、**cst_case**；**cst_base** 实现在 **constraint.sv**，含频率软约束、**mux.sel** 范围、**gate** 低功耗 **valid** 等。

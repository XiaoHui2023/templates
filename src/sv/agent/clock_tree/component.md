# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**callback** 注册、**trees** 访问、配置与 **operation** 便捷方法均在此句柄上 |
| **config_db** | 键 **`trees`**，值为 **base_tree** 队列；环境在例化 **agent** 前设置 |

环境先由 **connection** 建好各 **tree** 并 **randomize**，再通过 **config_db** 提供给 **agent** 后例化 **agent**。**agent** 将 **trees** 赋给 **sqr.trees**，不向基础 **sequencer** 传递。

## sequencer

基础 **sequencer**；**callback** 注册于此类型；**sequence** 的 **`p_sequencer`** 仅声明为此类型。不持有 **trees**。

| 方法 | 说明 |
| --- | --- |
| `apply_settings` | 对给定 **settings** 实例触发 **on_apply_settings**；仅声明 **setting_defs** 时存在 |

## kit_sequencer

派生 **sequencer**；**agent.sqr** 的实际类型。持有 **trees[$]**；配置与 **sequence/operation** 的便捷入口均在本类。

| 成员 | 说明 |
| --- | --- |
| `trees` | **base_tree** 队列，由 **agent.build_phase** 赋值 |

| 方法 | 说明 |
| --- | --- |
| `apply_settings` | 入参 **settings**；触发 **on_apply_settings**。**settings** 为空时对 **trees** 逐棵执行各 **tree.settings**；仅声明 **setting_defs** 时存在 |
| `set_clock_gen` | 入参 **nodes**、**gen_en** 默认 1；对带 **vif** 的节点启动 **set_clock_gen**。**nodes** 为空时对 **trees** 逐棵执行该树全部 **nodes** |
| `gen_source_clock` | 无参；收集 **trees** 中全部 **source** 后调用 **set_clock_gen** |
| `set_pll` | 入参 **pll** 节点；启动 **set_pll**，寄存器细节待补 |
| `configure` | 入参 **nodes**；启动 **configure**。**nodes** 为空时对 **trees** 逐棵执行 |
| `check_clk` | 入参 **nodes**；检查其中 **clk** 节点频率。**nodes** 为空时对 **trees** 逐棵执行 |
| `check_pll` | 入参 **nodes**；检查其中 **pll** 节点频率。**nodes** 为空时对 **trees** 逐棵执行 |
| `check_duty` | 入参 **nodes**；检查带 **vif** 节点占空比。**nodes** 为空时对 **trees** 逐棵执行 |
| `test_duty_wavefront` | 入参 **nodes**；按 **source** 依赖自前向后分波：**check_duty** 后对该波 **set_clock_gen**。**nodes** 为空时对 **trees** 逐棵执行 |

## sequence · operation

每种底层操作独占 **`sequence/operation/<操作名>/`**，含 **req**、**rsp** 与 **operation** 序列。**operation** 的 **`p_sequencer`** 类型为 **sequencer**，不得引用 **kit_sequencer** 或调用 kit 便捷方法。测试平台通过 **kit** 填 **req** 后 **start** 该序列。

| 行为目录 | 说明 |
| --- | --- |
| `set_clock_gen` | 按 **req.gen_en** 与节点 **frequence** 设置 **vif** 时钟发生；**gen_en** 为 0 关闭 |
| `set_pll` | **pll** 频率与寄存器配置，主体待补 |
| `configure` | 写入 **gate**、**div**、**dto**、**mux** 配置寄存器，主体待补；**req.nodes** 指定范围 |
| `check_clk` | 检查 **req.nodes** 中 **clk** 频率 |
| `check_pll` | 检查 **req.nodes** 中 **pll** 频率 |
| `check_duty` | 检查 **req.nodes** 中带 **vif** 节点占空比 |

## sequence · test

组合测试序列放在 **`sequence/test/<测试名>/`**，含 **req**、**rsp** 与 **test** 序列；**p_sequencer** 仍为 **sequencer**，在 **body** 内 **start** 多个 **operation** 序列。

| 测试目录 | 说明 |
| --- | --- |
| `test_duty_wavefront` | 在 **req.nodes** 上按波前顺序：**check_duty** → **set_clock_gen**，再处理下一波下游节点 |

## sequence · base

**base_seq** 派生 **spec**，类型实参为 **uvm_sequence**。**base_seq** 的 **`p_sequencer`** 类型为 **sequencer**。

## tree 外部约束

每棵 **{name}_tree** 声明 **cst_base**、**cst_user**、**cst_case**；**cst_base** 实现在 **constraint.sv**，含频率软约束、**mux.sel** 范围等。**clk** 与 **low_power** 的 **valid** 关系在 **base_tree** 的 **cst_base_tree**。

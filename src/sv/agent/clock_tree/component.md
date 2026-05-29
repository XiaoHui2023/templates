# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**；每个 **agent** 绑定单棵 **tree**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**tree** 访问、配置与 **operation** 便捷方法均在此句柄上 |
| **config_db** | 键 **`tree`**，值为 **base_tree** 实例；环境在例化 **agent** 前设置 |

环境创建 **tree**、调用 **build(regmodel)**，再 **connect_{name}_tree** 挂 **vif**，**randomize** 在 **build** 内完成；通过 **config_db** 提供给 **agent** 后例化 **agent**。**agent** 将 **tree** 赋给 **sqr.tree**，不向基础 **sequencer** 传递。

## sequencer

基础 **sequencer**；**sequence** 的 **`p_sequencer`** 仅声明为此类型。不持有 **tree**。**build_phase** 例化 **tools**，类型 **core_tools**，供 **config_reg** 等写 RAL 与 PLL 的 sequence 使用。

| 成员 | 说明 |
| --- | --- |
| `tools` | **core_tools**：**reg**、**node**、**pll** 三类寄存器与 PLL 工具 |

## kit_sequencer

派生 **sequencer**；**agent.sqr** 的实际类型。持有 **tree**；配置与 **sequence/operation** 的便捷入口均在本类。

| 成员 | 说明 |
| --- | --- |
| `tree` | **base_tree** 实例，由 **agent.build_phase** 赋值 |

| 方法 | 说明 |
| --- | --- |
| `set_clock_gen` | 入参 **nodes**、**gen_en** 默认 1；对带 **vif** 的节点启动 **set_clock_gen**。**nodes** 为空时对 **tree.nodes** 执行 |
| `gen_source_clock` | 无参；收集 **tree** 中全部 **source** 后调用 **set_clock_gen** |
| `config_reg` | 入参 **nodes**；启动 **config_reg**。**nodes** 为空时对 **tree.nodes** 执行；含 **pll** 写 RAL 与 **wait_lock** |
| `check_clk` | 入参 **nodes**；检查其中 **clk** 节点频率。**nodes** 为空时对 **tree.nodes** 执行 |
| `check_pll` | 入参 **nodes**；检查其中 **pll** 节点频率。**nodes** 为空时对 **tree.nodes** 执行 |
| `check_duty` | 入参 **nodes**；检查带 **vif** 节点占空比。**nodes** 为空时对 **tree.nodes** 执行 |
| `test_duty_wavefront` | 入参 **nodes**；按 **source** 依赖自前向后分波：**check_duty** 后对该波 **set_clock_gen**。**nodes** 为空时对 **tree.nodes** 执行 |

## sequence · operation

每种底层操作独占 **`sequence/operation/<操作名>/`**，含 **req**、**rsp** 与 **operation** 序列。**operation** 的 **`p_sequencer`** 类型为 **sequencer**，不得引用 **kit_sequencer** 或调用 kit 便捷方法。测试平台通过 **kit** 填 **req** 后 **start** 该序列。

| 行为目录 | 说明 |
| --- | --- |
| `set_clock_gen` | 按 **req.gen_en** 与节点 **frequence** 设置 **vif** 时钟发生；**gen_en** 为 0 关闭 |
| `config_reg` | 对 **gate**、**mux**、**div**、**dto**、**pll** 写 RAL，通过 **p_sequencer.tools**；**pll_sc** / **pll_dw** 按目标频率算分频后上电；**pll** 配完后 **wait_lock** |
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

**{name}_tree** 声明 **cst_base**、**cst_user**、**cst_case**；**cst_base** 实现在 **constraint.sv**，含频率软约束；**mux** 配置了 **source** 时生成 **sel inside**。**clk** 与 **low_power** 的 **valid** 关系在 **base_tree** 的 **cst_base_tree**。

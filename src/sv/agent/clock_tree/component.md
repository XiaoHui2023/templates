# UVM 组件

展开类型名带 **class_prefix** 前缀；下文标题与表仅用后缀名。

## agent

每个 **agent** 绑定单棵 **tree**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄 |
| **config_db** | 键 **`tree`**，值为 **tree_base** 实例；例化 **agent** 前由环境设置 |

环境创建 **tree**、调用 **build** 绑定寄存器模型，再 **connect_{name}_tree** 挂 **vif**。**agent** 将 **tree** 赋给 **sqr.tree**。

## sequencer

**sequence** 的 **`p_sequencer`** 声明为本类型；不持有 **tree**。

| 成员 | 说明 |
| --- | --- |
| `tools` | **core_tools**：**rw**、**node**、**pll** |

## kit_sequencer

**agent.sqr** 的类型；持有 **tree**，由 **agent.build_phase** 赋值。

**config_reg**、**check_freq**、**check_duty**、**test_freq**、**test_duty**、**test_flip**、**test_route** 均 **start** 同名序列；**tree** 入参默认空则用 **kit.tree**。**test_route** 入参除 **tree** 外还有 **always_active_clk_nodes** 队列，默认空。

## sequence · base

**base_seq** 派生 **spec**，类型实参 **uvm_sequence**；**p_sequencer** 为 **sequencer**。

**operation** 与 **test** 序列不得 **`$cast`** 到 **kit_sequencer**，不得调用 kit 便捷 **task**。**kit** 填 **req** 后 **start**，或由 kit 同名 **task** 代填。**req.quiet** 为 1 时不打印 **uvm_info** 进度行；**uvm_error** / **uvm_fatal** 照常。

## sequence · operation

**`sequence/operation/<操作名>/`** 含 **req**、**rsp**、**op**。

| 行为目录 | 说明 |
| --- | --- |
| `config_reg` | 写 **req.tree** 寄存器 |
| `check_freq` | 量 **source**、**clk**、**pll** 频率 |
| `check_duty` | 量带 **vif** 节点占空比 |

## sequence · test

**`sequence/test/<测试名>/`** 含 **req**、**rsp**、**test** 序列；**body** 内 **start** 多个 **operation** 序列。

| 测试目录 | 说明 |
| --- | --- |
| `test_freq` | **config_reg** 后 **check_freq** |
| `test_duty` | **config_reg** 后 **check_duty** |
| `test_flip` | 分频比翻转探测 |
| `test_route` | 结构探测 |

## tree 外部约束

**{name}_tree** 含 **cst_base**、**cst_user**、**cst_case**；用例约束写在 **cst_user**、**cst_case**。**cst_base** 留作扩展口。建树 **new** 写入 **classic_frequence**、**max_sel**；**low_power** 与 **clk.valid** 见 **cst_tree_base**。

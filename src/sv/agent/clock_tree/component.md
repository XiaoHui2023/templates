# UVM 组件

## agent

每 **agent** 绑定单棵 **tree**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄 |
| **config_db** | 键 **`tree`**，值为 **tree_base** 实例；例化 **agent** 前由测试平台设置 |

测试平台创建 **tree**、**build** 绑定寄存器模型，再 **connect_{name}_tree** 挂 **vif**。

## sequencer

**sequence** 的 **`p_sequencer`** 为本类型；不持有 **tree**。

| 成员 | 说明 |
| --- | --- |
| `tools` | **core_tools**：**rw**、**node**、**pll** |

## kit_sequencer

**agent.sqr** 类型；持有 **tree**，**agent.build_phase** 赋值。

## sequence

**base_seq** 派生 **spec**，类型实参 **uvm_sequence**；**p_sequencer** 为 **sequencer**。

**operation**、**test** 序列不得 **`$cast`** 到 **kit_sequencer**，不得调用 kit 便捷 **task**。**kit** 填 **req** 后 **start**，或由 kit 同名 **task** 代填。**req.quiet** 为 1 时不打印 **uvm_info** 进度行；**uvm_error** / **uvm_fatal** 照常。

## tree 随机约束

**{name}_tree** 声明 **cst_base**、**cst_user**、**cst_case**；用例写在 **cst_user**、**cst_case**。

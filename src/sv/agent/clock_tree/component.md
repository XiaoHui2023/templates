# UVM 组件

展开类型名带 **class_prefix** 前缀。

## agent

时钟树 **UVM agent**；每个 **agent** 绑定单棵 **tree**。

| 成员 / 配置 | 说明 |
| --- | --- |
| `sqr` | **kit_sequencer** 句柄；**tree** 访问、配置与 **operation** 便捷方法均在此句柄上 |
| **config_db** | 键 **`tree`**，值为 **tree_base** 实例；环境在例化 **agent** 前设置 |

环境创建 **tree**、调用 **build(regmodel)**，再 **connect_{name}_tree** 挂 **vif**；通过 **config_db** 提供给 **agent** 后例化 **agent**。**agent** 将 **tree** 赋给 **sqr.tree**，不向基础 **sequencer** 传递。**randomize** 仅在 **config_reg** 写寄存器前对 **req.tree** 执行一次。

## sequencer

基础 **sequencer**；**sequence** 的 **`p_sequencer`** 仅声明为此类型。不持有 **tree**。**build_phase** 例化 **tools**，类型 **core_tools**，供 **config_reg** 等写寄存器模型与 PLL 的 sequence 使用。

| 成员 | 说明 |
| --- | --- |
| `tools` | **core_tools**：**rw**、**node**、**pll** 三类寄存器与 PLL 工具 |
| `tools.rw` | **reg_rw**：**set_write** / **write** 写总线前 **ensure_read** 刷新镜像；**apply** 对同一 **uvm_reg** 只读一次再合并各 field **set**；**has_read** 置位；目标值与 **get** 相同则跳过总线写；**get** / **set** 仅访问镜像时为 **function** |

## kit_sequencer

派生 **sequencer**；**agent.sqr** 的实际类型。持有 **tree**；配置与 **sequence/operation** 的便捷入口均在本类。

| 成员 | 说明 |
| --- | --- |
| `tree` | **tree_base** 实例，由 **agent.build_phase** 赋值 |

| 方法 | 说明 |
| --- | --- |
| `config_reg` | **task**；入参 **tree** 默认空，空时用 **kit** 上 **tree**；写 **tree.nodes** 全部寄存器前对 **tree** 执行一次 **randomize**；不向测试平台返回 **rsp** |
| `check_freq` | **task**；入参 **tree** 默认空，空时用 **kit** 上 **tree**；检查 **tree.nodes** 中 **source**、**clk**、**pll** 节点频率 |
| `check_duty` | **task**；入参 **tree** 默认空，空时用 **kit** 上 **tree**；检查 **tree.nodes** 中带 **vif** 节点占空比 |
| `check_flip` | **task**；入参 **tree** 默认空，空时用 **kit** 上 **tree**；全部 **clk** **unfix_frequence** 为 1 后对带绑定寄存器的 **div**、**dto** 分频寄存器 field 最高位写 1 其余写 0，**config_reg** 后 **check_freq**，再恢复并撤销 **fix_ratio**；结束时清除 **unfix_frequence** |
| `test_route` | **task**；入参 **tree** 默认空、**always_active_clk_nodes** 为须全程保持活动的 **clk** 句柄队列，默认空；依赖 **fix_*** 与 **config_reg**、**check_freq**，按节点验证上下游通路结构。**tree** 为空时用 **kit** 上 **tree** |

## sequence · operation

每种底层操作独占 **`sequence/operation/<操作名>/`**，含 **req**、**rsp** 与 **op**。**op** 内 **`p_sequencer`** 类型为 **sequencer**，不得引用 **kit_sequencer** 或调用 kit 便捷方法。测试平台通过 **kit** 填 **req** 后 **start** 该序列。**req.quiet** 为 1 时不打印 **uvm_info** 进度行，供 **test** 等上层封装时减少重复日志；**uvm_error** / **uvm_fatal** 不受影响。

| 行为目录 | 说明 |
| --- | --- |
| `config_reg` | 对 **req.tree** 执行一次 **randomize** 后，遍历 **tree.nodes** 写寄存器模型，通过 **p_sequencer.tools**；固定五段顺序：全部 **pll** 写寄存器后统一 **wait_lock**；全部 **div** 与 **dto**；**gate** 且 **open** 为真；全部 **mux**；**gate** 且 **open** 为假。**pll** **valid** 为 0 时跳过写寄存器与 **wait_lock**；参考与输出频率均未变时亦跳过；**pll_sc** / **pll_dw** 按目标频率算分频后上电 |
| `check_freq` | 遍历 **req.tree.nodes**，检查 **source**、**clk**、**pll** 频率 |
| `check_duty` | 遍历 **req.tree.nodes**，检查带 **vif** 节点占空比 |
| `check_flip` | 全部 **clk** **unfix_frequence** 为 1；对 **req.tree** 内带绑定寄存器的 **div**、**dto** 用 **fix_ratio** 固定分频比为寄存器 field 仅最高位为 1 时的值，**config_reg** 后 **check_freq**，再恢复；结束时清除 **unfix_frequence** |

## sequence · test

组合测试序列放在 **`sequence/test/<测试名>/`**，含 **req**、**rsp** 与 **test** 序列；**p_sequencer** 仍为 **sequencer**，在 **body** 内 **start** 多个 **operation** 序列。须 **tree** 等上下文时写入 **req**，由 **kit** 在 **start** 前补全默认值；**test** 序列内不得 **`$cast`** 到 **kit_sequencer** 或调用 **kit** 便捷方法。

| 测试目录 | 说明 |
| --- | --- |
| `test_route` | 初始 **fix_*** 后 **config_reg**、**check_freq**；**req.always_active_clk_nodes** 非空时只校验所列 **clk** 并保持活动，探测时全部 **clk** **unfix_frequence** 为 1，仅所列 **clk** **unfix_enabled** 为 0；跳过必启 **clk** 通路上的 **gate** / **mux** **subject** 及会关断必启 **clk** 的组合；对其余带寄存器的 **gate**、**mux**、**div**、**dto** 做上下游线探测；**req.quiet** 为 0 时按四段主流程与探测细目打印 **uvm_info** |

## sequence · base

**base_seq** 派生 **spec**，类型实参为 **uvm_sequence**。**base_seq** 的 **`p_sequencer`** 类型为 **sequencer**。

## tree 外部约束

**{name}_tree** 声明 **cst_base**、**cst_user**、**cst_case**；频率与 **mux.sel** 默认规则在节点类与 **new** 赋值，**cst_base** 仅作外部约束口供用例扩展。**new** 中为 **clk**、**pll**、**source** 写入 **classic_frequence**，为 **mux** 写入 **max_sel**。**clk** 与 **low_power** 的 **valid** 关系在 **tree_base** 的 **cst_tree_base**。

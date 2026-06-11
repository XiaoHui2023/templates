# 测试方法

时钟树 **agent** 的测试目标是核对三件事：寄存器写入后的可调节点状态、波形频率、占空比。

## 前提

使用者按芯片时钟树设计图填写节点名、前级关系、目标频率、门控开闭、多路选择、PLL 型号与寄存器路径。测试只判断仿真行为是否与这份理想配置一致。

两个 **gate** 串联且同开同关时，先后顺序不影响时钟是否通过。**inv** 只改变相位，不改变频率与门控语义。寄存器模型里未描述的保留位不纳入测试目标。

配置中的每棵 **tree** 按有向树处理：每个节点至多一个当前前级。**mux** 可以有多个输入，但 **sel** 与 **to_source[sel]** 唯一决定当前前级。

![使用者视角：设计图、配置、仿真核对](images/test_user_perspective.drawio.svg)

![树状拓扑与网状反例](images/test_tree_topology.drawio.svg)

![串联门控顺序可忽略](images/test_gate_series.drawio.svg)

## 测试分层

| 层级 | 目录 | 职责 |
| --- | --- | --- |
| **operation** | `sequence/operation/<名>/` | 单一可见动作 |
| **test** | `sequence/test/<名>/` | 组合 operation 覆盖常见场景 |

## test 序列

至少一处节点配置 **path** 时，下列 **test** 文件进入 **all.f**。

| 名称 | 调用 | 组合 |
| --- | --- | --- |
| **test_freq** | **test_freq** | **config_reg** 后 **check_freq** |
| **test_duty** | **test_duty** | **config_reg** 后 **check_duty** |
| **test_flip** | **test_flip** | 固定路由后翻转 **div** / **dto** 分频控制，再 **check_freq** |
| **test_route** | **test_route** | 遍历可调节点局部上下游结构，再 **check_freq** |

所有 **test** 的 **tree** 入参可空；为空时使用 **kit** 上绑定的 **tree**。**rsp.ok** 汇总结果。

## test_freq

先调用 **config_reg** 写寄存器，再调用 **check_freq** 校验 **source**、**clk**、**pll** 频率。

| 失败条件 | 行为 |
| --- | --- |
| **tree** 为空 | **fatal** |
| **config_reg** 或 **check_freq** 失败 | **fatal** |

## test_duty

先调用 **config_reg** 写寄存器，再调用 **check_duty** 校验所有带 **vif** 节点的占空比。

| 失败条件 | 行为 |
| --- | --- |
| **tree** 为空 | **fatal** |
| **config_reg** 失败 | **fatal** |
| **check_duty** 失败 | **rsp.ok** 为 0 |

## test_flip

**test_flip** 用于确认 **div**、**dto** 的分频寄存器 field 有效。探测时锁定 **gate** 与 **mux**，只改变当前 **div** 或 **dto** 的 **fix_ratio**。

流程：

1. **config_reg** 建立基线配置。
2. 按当前 **open**、**sel** 固定整树 **gate** 与 **mux**。
3. 全部 **clk** 的 **unfix_frequence** 置 1。
4. 对每个已绑定寄存器的 **div**、**dto** 保存控制量快照。
5. 将 **fix_ratio** 设为 field 最高有效位对应分频比。
6. 调用 **config_reg** 与 **check_freq**。
7. 恢复快照并再次 **config_reg**。
8. 清除全部 **fix_*** 与 **clk** **unfix_***，再 **config_reg**。

| 依赖 | 角色 |
| --- | --- |
| **config_reg** | 建立基线、写入探测分频比、恢复控制量 |
| **check_freq** | 核对分频比写入后的频率 |

| 失败条件 | 行为 |
| --- | --- |
| **tree** 为空 | **fatal** |
| 无已绑定寄存器的 **div** 或 **dto** | **fatal** |
| **config_reg** 或 **check_freq** 失败 | **fatal** |

## test_route

**test_route** 用于确认可调节点在树中的前后级关系。调用前宜让各 **div**、**dto** 分频比为 1，各 **PLL** 目标频率彼此不同且不同于晶振频率，便于频率区分。

![subject 节点视角：强调穿过 subject 节点的支路](images/test_route.drawio.svg)

流程：

1. **config_reg** 建立基线，使 **mux.sel** 与当前 **source** 链一致。
2. 按 **always_active_clk_nodes** 收集必启 **clk** 的选通链。
3. 选通链上的 **gate** 与 **mux** 固定，不作为 **subject**。
4. 其余已绑定寄存器的 **gate**、**mux**、**div**、**dto** 依次作为 **subject**。
5. 对每个 **subject** 分别探测上游与下游。
6. 对 **subject** 自身状态与线上的其它可调节点做组合。
7. 每个组合 **config_reg** 后 **check_freq**。
8. 会使必启 **clk** 失活的组合跳过。
9. 清除全部固定量，再 **config_reg** 收尾。

| 节点 | 自身状态 |
| --- | --- |
| **gate** | 开、关 |
| **mux** | 各 **sel** |
| **div** | 分频比 1、2 |
| **dto** | 分频比 1、2 |

| 依赖 | 角色 |
| --- | --- |
| **config_reg** | 每个组合写入整棵 **tree** |
| **check_freq** | 每个组合后核对频率传播 |

| 失败条件 | 行为 |
| --- | --- |
| **tree** 为空 | **fatal** |
| 无已绑定寄存器的 **gate** / **mux** / **div** / **dto** | **fatal** |
| **config_reg** 或 **check_freq** 失败 | **fatal** |

## 判定边界

| 覆盖项 | 判定 |
| --- | --- |
| 寄存器写入 | **config_reg** 成功 |
| 频率 | **check_freq** 与 **_resolved_freq** 一致 |
| 占空比 | **check_duty** 与上下限一致 |
| 局部路由 | **test_route** 的上下游组合均通过 |
| 分频控制位 | **test_flip** 的最高有效位探测通过 |

| 范围外 | 原因 |
| --- | --- |
| 网状重汇 | 不满足树状拓扑前提 |
| 异步跨时钟域 | 不属于时钟树配置核对 |
| 门控物理差异导致的占空比畸变 | 由占空比测量结果体现，不拆成结构判断 |
| 未配置 **path** 的节点 | 没有可测量接口 |

## 用例形状

| 场景 | 配置要点 | 调用 |
| --- | --- | --- |
| 单树端到端 | 各 **kind** 至少一个，部分节点带 **path**，部分节点带 **reg** 或 **regs** | **test_freq** 后 **test_duty** |
| 通路结构 | **gate**、**mux**、**div**、**dto** 分别有可测路径与寄存器 | **test_freq** 通过后 **test_route** |
| PLL 路径 | **pll** 与 **source**，寄存器 field 齐全 | **test_freq** |
| 门控全关 | 多个 **gate** 串联，**open** 随机 | **test_freq** |
| 固定 mux | 节点带 **path** 与 **reg**，测试前设置 **fix_sel** | **test_freq** |
| 固定 div 分频 | 节点带 **path** 与 **regs**，测试前设置 **fix_ratio** | **test_freq** |

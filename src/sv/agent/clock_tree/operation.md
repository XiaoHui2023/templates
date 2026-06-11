# operation

时钟树 **agent** 在 **kit_sequencer** 上提供与 **sequence/operation** 目录同名的 **task**。测试平台在 **agent.sqr** 上调用；**tree** 入参默认空时用 **kit** 上绑定的 **tree**。

## 调用约定

| 项 | 说明 |
| --- | --- |
| 入口 | **kit_sequencer** 上与操作同名的 **task** |
| **tree** | 默认空时用 **kit** 上 **tree**；一次 **start**，**req.tree** 指定待处理整棵树 |

至少一处节点配置了 **path** 才会生成 **check_freq** 与 **check_duty**。配置 **class_regmodel** 且节点绑定了 **regs** 时才会生成 **config_reg**。

## 操作一览

| 名称 | 作用 |
| --- | --- |
| **config_reg** | 把节点目标值写入寄存器模型；顺序为 **pll** → **div** / **dto** → 开 **gate** → **mux** → 关 **gate**，见下节 |
| **check_freq** | 测量 **source**、**clk**、**pll** 波形频率，与节点 **frequence** 比较 |
| **check_duty** | 测量带 **vif** 节点的占空比，与 **duty_min**、**duty_max** 闭区间比较，端点计入合格 |

容差与占空比上下限在 **settings** 的 **period_tolerance**、**duty_min**、**duty_max**；**duty_min**、**duty_max** 为百分数；PLL 等锁超时为 **pll_lock_timeout_us**。

## config_reg

通过 **sequencer.tools** 写寄存器模型，只更新约定 field，field 内其余位保持不变。

写入分五段，遍历 **tree.nodes**：

1. 全部 **pll** 寄存器，再对本轮全部 **pll** **wait_lock**
2. 全部 **div**、**dto**
3. **open** 为真的 **gate**
4. 全部 **mux**
5. **open** 为假的 **gate**

**pll** 分频用 **source.frequence** 与节点 **frequence**；缺 **source** 或频率非法则 **fatal**。参考频率与输出 **frequence** 均与 **sequencer.tools.pll** 中按节点名记录的上次写入相同时跳过寄存器更新，且不再 **wait_lock**。

**div**、**dto** 默认不走 **rst** 流程，**config_reg** 只更新分频 field 与 **load** 脉冲。**reset_div_on_first_config** 或 **reset_dto_on_first_config** 为真时，**sequencer.tools.node** 按节点名记录是否已走过 **rst** 释放；每个节点首次 **config_reg** 走完整 **rst** 流程，之后同一 **sequencer** 生命周期内再次 **config_reg** 不再拉 **rst**。

### 注意

+ 器件上 **div** 常默认处于复位态，分频输出不工作；**mux** 若先切到该支路，选中路径上可能长时间无有效时钟或频率不对。
+ **config_reg** 固定把 **div**、**dto** 写在 **mux** 之前，让分频在 **mux** 选中该支路前就绪。
+ **dto** 同样有 **rst** 释放流程，与 **div** 同属第 2 段，理由相同。

## check_freq

只测量，不写寄存器。遍历 **req.tree.nodes**，只处理 **kind** 为 **source**、**clk** 或 **pll** 且已挂 **vif** 的项。**req.min_freq_hz** 为 0 时用 **settings.min_freq_hz**；测量前对各 **vif** 调用 **set_min_freq_hz** 与序列轮询共用该值推导超时。

先对全部目标节点 **start_measure**，再按轮询 **stable**：**stable** 含连续周期稳定与无有效边沿超时两种结束方式。某节点 **stable** 后按 **_resolved_active** 与 **active**、**freq_hz** 判定：期望无时钟时要求 **active** 为假；期望有时钟时要求 **active** 为真且 **freq_hz** 与 **_resolved_freq** 相对偏差不超过 **period_tolerance**。未 **stable** 的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未 **stable** 则报错。

写寄存器后再量频用 **test_freq**。

## check_duty

只测量，不写寄存器。遍历 **req.tree.nodes**，处理已挂 **vif** 的节点，不限 **kind**。先对全部目标节点 **start_measure**，再按轮询 **stable**：某节点一旦稳定即根据 **vif.meas.duty_ok** 判定并 **stop_measure** 该节点；未稳定的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未稳定的节点报错。范围由 **duty_min**、**duty_max** 决定。未通过占空比的节点记入 **rsp.failed_nodes**。

写寄存器后再量占空比用 **test_duty**。

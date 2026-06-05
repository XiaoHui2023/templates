# operation

时钟树 **agent** 在 **kit_sequencer** 上提供与 **sequence/operation** 目录同名的 **task**。测试平台在 **agent.sqr** 上调用；**nodes** 默认为空队列时表示对该 **tree** 的全部节点生效。

## 调用约定

| 项 | 说明 |
| --- | --- |
| 入口 | **kit_sequencer** 上与操作同名的 **task** |
| **nodes** | 空队列时对 **tree.nodes** 整棵执行；非空时只处理列表中的节点 |
| 各操作 | 一次 **start**，**req.nodes** 携带整批节点 |

至少一处节点配置了 **path** 才会生成 **check_freq** 与 **check_duty**。配置 **class_regmodel** 且节点绑定了 **regs** 时才会生成 **config_reg**。

## 操作一览

| 名称 | 作用 |
| --- | --- |
| **config_reg** | 把节点目标值写入寄存器模型；顺序为 **pll** → **div** / **dto** → 开 **gate** → **mux** → 关 **gate**，见下节 |
| **check_freq** | 测量 **source**、**clk**、**pll** 波形频率，与节点 **frequence** 比较 |
| **check_duty** | 测量带 **vif** 节点的占空比，与 **duty_min**、**duty_max** 比较 |

容差与占空比上下限在 **settings** 的 **period_tolerance**、**duty_min**、**duty_max**；PLL 等锁超时为 **pll_lock_timeout_us**。

## config_reg

通过 **sequencer.tools** 写寄存器模型，只更新约定 field，field 内其余位保持不变。

写入分五段，与 **req.nodes** 下标无关：

1. 全部 **pll** 寄存器，再对本轮全部 **pll** **wait_lock**
2. 全部 **div**、**dto**
3. **open** 为真的 **gate**
4. 全部 **mux**
5. **open** 为假的 **gate**

**pll** 分频用 **source.frequence** 与节点 **frequence**；缺 **source** 或频率非法则 **fatal**。参考频率与输出 **frequence** 均与 **sequencer.tools.pll** 中按节点名记录的上次写入相同时跳过寄存器更新，且不再 **wait_lock**。

### 注意

+ 器件上 **div** 常默认处于复位态，分频输出不工作；**mux** 若先切到该支路，选中路径上可能长时间无有效时钟或频率不对。
+ **config_reg** 固定把 **div**、**dto** 写在 **mux** 之前，让分频在 **mux** 选中该支路前就绪。只把部分节点放进 **req.nodes**、或平台自行分批写寄存器时，仍应先配好路径上的 **div**、**dto**，再改 **mux** **sel**。
+ **dto** 同样有 **rst** 释放流程，与 **div** 同属第 2 段，理由相同。

## check_freq

只处理 **req.nodes** 里 **kind** 为 **source**、**clk** 或 **pll** 且已挂 **vif** 的项。先对全部待测节点 **start_measure**，再按轮询 **stable**：某节点一旦稳定即比较 **freq_hz** 与 **frequence** 并 **stop_measure** 该节点；未稳定的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未稳定的节点报错。超出 **period_tolerance** 则报错。

## check_duty

处理 **req.nodes** 里已挂 **vif** 的节点，不限 **kind**。先对全部待测节点 **start_measure**，再按轮询 **stable**：某节点一旦稳定即根据 **vif.meas.duty_ok** 判定并 **stop_measure** 该节点；未稳定的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未稳定的节点报错。范围由 **duty_min**、**duty_max** 决定。未通过占空比的节点记入 **rsp.failed_nodes**。

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

通过 **sequencer.tools** 写寄存器模型。每次只改约定 field 的切片，父寄存器其余位读回后合并再写。**set_write** 在镜像值未变时跳过总线写；**apply** 对多 field 先统一 **set** 再按父寄存器去重写一次。

**body** 先 **randomize** **tree**，再按下列五段遍历 **tree.nodes**：

1. 全部 **pll**，再对本轮实际写过寄存器的 **pll** **wait_lock**
2. 全部 **div**、**dto**
3. **open** 为真的 **gate**
4. 全部 **mux**
5. **open** 为假的 **gate**

### 寄存器访问

| 机制 | 说明 |
| --- | --- |
| **reg_rw.set_write** | 读镜像、合并切片、值变才前门写父寄存器 |
| **reg_rw.apply** | 多 field 批量 **set** 后按父寄存器合并写 |
| **sequencer.tools.pll** | 按节点名记上次 **ref_hz**、**out_hz**；二者均未变则跳过该 **pll** 写与 **wait_lock** |
| **sequencer.tools.node** | **mux** 记上次写入的 **sel** |

### 含复位或掉电的写

**mux**、**div**、**dto**、**pll** 凡要先拉复位或掉电再改其它 field，统一两步：

1. 第一次只写复位或掉电电平，常用 **set_write** 只动 **rst**、**reset**、**pd** 等单一控制位。
2. 第二次 **apply** 同时写取消复位或掉电与其余待配 field；同一父寄存器内能合并的不拆成多次总线写。

**load** 的 0→1 脉冲、**pll** **dw** 的固定延时等时序要求仍单独一步。每次 **config_reg** 对 **div**、**dto** 都走复位两步。**mux** **sel** 未变则整段跳过。

| 节点 | 第一次 | 第二次 **apply** 含 |
| --- | --- | --- |
| **mux** | 只写 **rst** 复位电平 | **rst** 不复位与 **sel** |
| **div** | 只写 **rst** 复位电平 | **rst** 不复位、**div**、**load**=0；再 **load**=1 |
| **dto** | 只写 **rst** 复位电平 | **rst** 不复位与 **load**/**bypass**/**step** |
| **pll tci** | 只写 **reset**=1 | 复位保持期间写 **bypass**/**pwrdn** 与分频 field；再一次 **apply** **reset**=0 与 **bypass**=0 |
| **pll sc** | 五路 **pd**/**bypass** 全 1 | 五路全 0 与 **refdiv**/**postdiv**/**fbdiv** |
| **pll dw** | 只写 **reset**=1 | **pwron**/**shift**/**bypass**；延时后 **reset**=0 与 **shift**=0 同次 **apply** |
| **pll inno** 共享级 | 只写 **pd**=1 | **pd**=0 与 **refdiv**/**fbdiv** |

### pll

参考时钟取 **source._resolved_freq**，目标频率取节点 **frequence**。**_resolved_active** 为假时跳过该 **pll**。缺 **source**、频率非正或绑定 field 不全则 **fatal**。

本轮写过寄存器的 **pll** 进入 **wait_lock** 队列；**pll_inno** 仅 **group_id** 为 0 的句柄入队并轮询 **f_lock**。轮询间隔 2 µs，上限 **pll_lock_timeout_us**，超时 **fatal**；成功后置 **locked** 为真。

| **pll_kind** | 分频算式 | 写寄存器顺序 |
| --- | --- | --- |
| **tci** | **clkr**=1，**clkod**=1，**clkf**=**out**/**ref**，**bwadj**=**clkf** | 见上表 **pll tci** 三步；分频 field 在 **reset** 保持期间写入 |
| **sc** | 在 **pll_sc_fbdiv_min**～**pll_sc_fbdiv_max** 内搜 **fbdiv**、**refdiv**、**postdiv1**、**postdiv2** 使 **ref**×**fbdiv**/**refdiv**/**postdiv1**/**postdiv2**≈**out** | 见上表 **pll sc** |
| **dw** | 由 **out**、**ref** 算 **fbdiv**、**prediv**、**divvcop**、**p**、**divvcor**、**r** | **fbdiv**/**prediv** → 见上表 **pll dw** → **divvcor**/**r**/**p**/**divvcop** → **enr**/**enp**=1 |
| **inno** | 共享级 **fbdiv**/**refdiv**；每路 **postdiv1**/**postdiv2** | **group_id**=0：见上表 **pll inno** 共享级，并写该路 **postdiv1**/**postdiv2**；**group_id**>0：读回共享 **fbdiv**/**refdiv**，只写该路 **postdiv1**/**postdiv2** |

### div

模型 **ratio** 为 1～64；寄存器 **div** field 写入 **n**=**ratio**−1，**ratio**=1 时 **n**=0。每次 **config_reg** 遵循上节 **div** 行。**rst** 极性由 **div_reg_high_means_reset** 决定。

### dto

| **ratio** | **load** | **bypass** | **step** |
| --- | --- | --- | --- |
| 1 | 1 | 1 | 0 |
| >1 | 1 | 0 | 2^25/**ratio**，整数落在 1～2^25−1 |

每次 **config_reg** 遵循上节 **dto** 行。**rst** 极性由 **dto_reg_high_means_reset** 决定。

### gate

按节点 **open** 写 **f_reg**。**gate_reg_high_means_open** 为真时寄存器值与 **open** 相同；为假时取反。

第 3 段只写 **open** 为真的 **gate**；第 5 段只写 **open** 为假的 **gate**。

### mux

**sel** 未变则跳过。**sel** 变更时遵循上节 **mux** 行；极性由 **mux_reg_high_means_reset** 决定。

### 写入顺序说明

+ 器件上 **div** 常默认处于复位态，分频输出不工作；**mux** 若先切到该支路，选中路径上可能长时间无有效时钟或频率不对。
+ 第 2 段固定在第 4 段之前，让分频在 **mux** 选中该支路前就绪。

## check_freq

只测量，不写寄存器。遍历 **req.tree.nodes**，只处理 **kind** 为 **source**、**clk** 或 **pll** 且已挂 **vif** 的项。**req.min_freq_hz** 为 0 时用 **settings.min_freq_hz**；测量前对各 **vif** 调用 **set_min_freq_hz** 与序列轮询共用该值推导超时。

先对全部目标节点 **start_measure**，再按轮询 **stable**：**stable** 含连续周期稳定与无有效边沿超时两种结束方式。某节点 **stable** 后按 **_resolved_active** 与 **active**、**freq_hz** 判定：期望无时钟时要求 **active** 为假；期望有时钟时要求 **active** 为真且 **freq_hz** 与 **_resolved_freq** 相对偏差不超过 **period_tolerance**。未 **stable** 的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未 **stable** 则报错。

写寄存器后再量频用 **test_freq**。

## check_duty

只测量，不写寄存器。遍历 **req.tree.nodes**，处理已挂 **vif** 的节点，不限 **kind**。先对全部目标节点 **start_measure**，再按轮询 **stable**：某节点一旦稳定即根据 **vif.meas.duty_ok** 判定并 **stop_measure** 该节点；未稳定的节点进入下一轮，直至全部测完或达到与 **min_freq_hz** 对应的超时；超时仍未稳定的节点报错。范围由 **duty_min**、**duty_max** 决定。未通过占空比的节点记入 **rsp.failed_nodes**。

写寄存器后再量占空比用 **test_duty**。

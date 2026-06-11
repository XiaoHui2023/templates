# operation

时钟树 **agent** 在 **kit_sequencer** 上提供与 **sequence/operation** 目录同名的 **task**。**tree** 入参为空时使用 **kit** 上绑定的 **tree**。

## 操作一览

| 名称 | 作用 |
| --- | --- |
| **config_reg** | 按节点目标值写寄存器模型 |
| **check_freq** | 测量 **source**、**clk**、**pll** 波形频率，与节点 **frequence** 比较 |
| **check_duty** | 测量带 **vif** 节点的占空比 |

| 操作 | 启用条件 |
| --- | --- |
| **config_reg** | 配置了寄存器模型类型，且至少一个节点绑定 **reg** 或 **regs** |
| **check_freq** | 至少一个节点配置 **path** |
| **check_duty** | 至少一个节点配置 **path** |

## config_reg

**config_reg** 先随机化 **tree**，再按 **pll**、**div** / **dto**、**mux** 切换准备、打开的 **gate**、**mux**、关闭的 **gate** 六段写寄存器。

| 段 | 节点 |
| --- | --- |
| 1 | 全部 **pll**；本轮实际写过寄存器的 **pll** 进入 **wait_lock** |
| 2 | 全部 **div**、**dto** |
| 3 | **sel** 将变化的 **mux**：打开其全部上游 **gate**，按最慢直接前级时钟等待 **mux_switch_wait_cycles** 个周期 |
| 4 | **open** 为真的 **gate** |
| 5 | 全部 **mux** |
| 6 | **open** 为假的 **gate**，含第 3 段临时打开的 **gate** |

**reg_rw.set_write** 读镜像、合并切片，值变化时写父寄存器。**reg_rw.apply** 对多个 field 先统一 **set**，再按父寄存器合并写。

### 复位与掉电

**div**、**dto**、**pll** 需要先拉复位或掉电时，第一次只写控制位，第二次 **apply** 同时写取消复位或掉电与其余 field。同一父寄存器内能合并的 field 不拆成多次总线写。

| 节点 | 第一次 | 第二次 |
| --- | --- | --- |
| **div** | 只写 **rst** 复位电平 | **rst** 不复位、**div**、**load**=0；再 **load**=1 |
| **dto** | 只写 **rst** 复位电平 | **rst** 不复位与 **load**/**bypass**/**step** |
| **pll tci** | **reset**=1 | 保持复位写 **bypass**/**pwrdn** 与分频 field；再写 **reset**=0 与 **bypass**=0 |
| **pll sc** | 五路 **pd**/**bypass** 全 1 | 五路全 0 与 **refdiv**/**postdiv**/**fbdiv** |
| **pll dw** | **reset**=1 | **pwron**/**shift**/**bypass**；延时后写 **reset**=0 与 **shift**=0 |
| **pll inno** 共享级 | **pd**=1 | **pd**=0 与 **refdiv**/**fbdiv** |

### pll

参考时钟取 **source._resolved_freq**，目标频率取节点 **frequence**。**_resolved_active** 为假时跳过该 **pll**。

缺 **source**、频率非正或绑定 field 不全时报 **fatal**。参考频率与目标频率均与上次记录相同，则跳过寄存器写与 **wait_lock**。

本轮写过寄存器的 **pll** 进入 **wait_lock** 队列。**pll_inno** 仅 **group_id** 为 0 的句柄轮询 **f_lock**。轮询间隔 2 us，上限 **pll_lock_timeout_us**；超时 **fatal**，成功后置 **locked** 为真。

| **pll_kind** | 分频算式 | 写入 |
| --- | --- | --- |
| **tci** | **clkr**=1，**clkod**=1，**clkf**=**out**/**ref**，**bwadj**=**clkf** | 分频 field 在 **reset** 保持期间写入 |
| **sc** | 搜索 **fbdiv**、**refdiv**、**postdiv1**、**postdiv2**，使 **ref**×**fbdiv**/**refdiv**/**postdiv1**/**postdiv2** 逼近 **out** | 写掉电与 bypass，再写分频 field |
| **dw** | 由 **out**、**ref** 算 **fbdiv**、**prediv**、**divvcop**、**p**、**divvcor**、**r** | 分段写 **fbdiv**/**prediv**、复位相关 field、后级分频与使能 |
| **inno** | 共享级 **fbdiv**/**refdiv**；每路 **postdiv1**/**postdiv2** | **group_id** 0 写共享级与本路；其余路读回共享级，只写本路 |

### div

**ratio** 为 1～64。寄存器 **div** field 写入 **n**=**ratio**−1；**ratio** 为 1 时 **n** 为 0。**should_reset_div** 为真时每次写入都执行复位两步；为假时首次不经复位脉冲，此后只更新 **div** 与 **load**。**rst** 极性由 **div_reg_high_means_reset** 决定。

### dto

| **ratio** | **load** | **bypass** | **step** |
| --- | --- | --- | --- |
| 1 | 1 | 1 | 0 |
| 大于 1 | 1 | 0 | 2^25/**ratio**，整数落在 1～2^25−1 |

**should_reset_dto** 为真时每次写入都执行复位两步；为假时首次不经复位脉冲，此后只更新 **load**、**bypass** 与 **step**。**rst** 极性由 **dto_reg_high_means_reset** 决定。

### gate

第 4 段只写 **open** 为真的 **gate**；第 6 段只写 **open** 为假的 **gate**。**gate_reg_high_means_open** 为真时寄存器值与 **open** 相同，为假时取反。

### mux

第 3 段仅处理 **sel** 与上次写入不同的 **mux**：沿各 **mux** 上游收集全部 **gate** 并写寄存器为打开；在全部待切换 **mux** 的直接前级里取最低 **_resolved_freq**，等待 **mux_switch_wait_cycles** 乘该时钟周期，多路取最长等待时间。全部 **mux** **sel** 均未变化时跳过第 3 段。

第 5 段写全部 **mux**：**sel** 与上次写入相同时跳过；否则写入 **sel** 寄存器。

## check_freq

**check_freq** 只测量，不写寄存器。目标节点为已挂 **vif** 的 **source**、**clk**、**pll**。

**min_freq_hz** 为 0 时使用 **settings.min_freq_hz**。测量前对各 **vif** 调用 **set_min_freq_hz**，序列轮询也用该值推导超时。

流程：

1. 对全部目标节点 **start_measure**。
2. 轮询 **stable**。
3. 期望无时钟时要求 **active** 为假。
4. 期望有时钟时要求 **active** 为真，且 **freq_hz** 与 **_resolved_freq** 相对偏差不超过 **period_tolerance**。
5. 超时仍未 **stable** 的节点报错。

## check_duty

**check_duty** 只测量，不写寄存器。目标节点为已挂 **vif** 的节点，不限制 **kind**。

流程：

1. 对全部目标节点 **start_measure**。
2. 轮询 **stable**。
3. 节点稳定后按 **vif.meas.duty_ok** 判定并 **stop_measure**。
4. 未通过占空比的节点记入 **rsp.failed_nodes**。
5. 超时仍未 **stable** 的节点报错。

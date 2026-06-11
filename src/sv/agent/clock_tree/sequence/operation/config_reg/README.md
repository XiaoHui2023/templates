# config_reg

写寄存器

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 减少 **UVM** 日志 |

## 流程

![config_reg 流程](../../../images/config_reg_flow.drawio.svg)

### 复位与掉电

**div**、**dto**、**pll** 需要先拉复位或掉电时，第一次只写控制位，第二次同时写取消复位或掉电与其余 field。同一父寄存器内能合并的 field 不拆成多次总线写。

| 节点 | 第一次 | 第二次 |
| --- | --- | --- |
| **div** | 只写 **rst** 复位电平 | **rst** 不复位、**div**、**load**=0；再 **load**=1 |
| **dto** | 只写 **rst** 复位电平 | **rst** 不复位与 **load**/**bypass**/**step** |
| **pll tci** | **reset**=1 | 保持复位写 **bypass**/**pwrdn** 与分频 field；再写 **reset**=0 与 **bypass**=0 |
| **pll sc** | 五路 **pd**/**bypass** 全 1 | 五路全 0 与 **refdiv**/**postdiv**/**fbdiv** |
| **pll dw** | **reset**=1 | **pwron**/**shift**/**bypass**；延时后写 **reset**=0 与 **shift**=0 |
| **pll inno** 共享级 | **pd**=1 | **pd**=0 与 **refdiv**/**fbdiv** |

### pll

参考时钟取前级解析频率，目标频率取节点 **frequence**。节点不活动时跳过该 **pll**。

缺前级、频率非正或寄存器 field 不全时终止。参考频率与目标频率均与上次相同，则跳过写寄存器与等待锁定。

本轮写过寄存器的 **pll** 进入等待锁定队列。**pll_inno** 仅 **group_id** 为 0 的句柄轮询锁定位。轮询间隔 2 us，上限 **pll_lock_timeout_us**；超时终止，成功后置 **locked** 为真。

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

第 3 段仅处理 **sel** 将变化的 **mux**：沿各 **mux** 上游收集全部 **gate** 并写为打开；在全部待切换 **mux** 的直接前级里取最低频率，等待 **mux_switch_wait_cycles** 乘该时钟周期，多路取最长等待时间。全部 **mux** **sel** 均未变化时跳过第 3 段。

第 5 段写全部 **mux**：**sel** 与上次写入相同时跳过；否则写入 **sel** 寄存器。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 无错误时为真 |

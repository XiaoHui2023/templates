# flip_check

串行检查可编程器件的功能。先对整树执行一次低功耗配置，再逐个节点切换控制值并检查输出。

测试后恢复的是**低功耗配置之后、该节点测试之前**的控制切片，不恢复调用flip之前的整树状态。stable时钟及其上游、共享受保护控制字段的节点不参与。

## 调用

tree已build，agent构建完成后，在task中调用：

```systemverilog
clk_tree_flip_check_req req;
clk_tree_flip_check_seq seq;

req = clk_tree_flip_check_req::type_id::create("req");
req.tree = tree;
seq = clk_tree_flip_check_seq::type_id::create("flip");
seq.req = req;
seq.start(clk_agt.sqr);
if (seq.rsp != null)
    `uvm_info("CLOCK", $sformatf("failed %0d", seq.rsp.failed), UVM_LOW)
```

请求只有tree。快捷调用为 `clk_agt.sqr.test_flip()`；失败汇总后，快捷task报告fatal。

## 单个节点

1. 真实读取控制寄存器，保存绑定切片。
2. 直连时钟源、`allow_override=0` 或已有驱动的输入只测量，不 force。其余输入可由测试驱动；mux 为这些输入分配不同频率。
3. 写当前器件控制值，等待生效，检查输出活动、频率和允许检查的占空比。
4. 写回保存的切片，执行必要的load、复位及等待。
5. 只释放本次测试施加的驱动，继续下一个节点。

配置和恢复期间保持force，不为寄存器访问临时释放。初次低功耗配置后，不再调用全树configure。检查失败仍执行局部恢复并累计；仿真终止或总线致命错误不保证恢复。

## 已实现的覆盖

| 节点 | 检查 |
| --- | --- |
| gate | 打开有时钟、关闭无活动 |
| div_div | 按绑定字段位宽逐位写one-hot编码，检查分频输出 |
| div_dto | 旁通、step各位的0/1及互补模式，按折叠频率检查 |
| clk_div_with_clken | 遍历16个编码，检查三个输出 |
| mux、inv_mux | 遍历可选输入，检查选路频率与占空比 |
| inv、inv_cell | 分别写入直通和反相编码，在输入高、低脉冲的中心检查输出电平，再检查输出频率和占空比 |

div_div、DTO和clk_div_with_clken不检查功能输出占空比。其他插件可用output_duty_check_enabled按端口关闭。

div每次写分频值前复位，再写分频值与load，等待后测量。DTO共用普通配置的step、bypass、load同步流程。反相器使用插件配置的极性编码和写入等待；信号传播需在输入脉冲中心采样前完成。mux切换后固定等待70ns。

完整25位DTO测试保持输出在输入频率的约1/4至1/2，避免接近零频率。每位都写过0和1，不等于在当前测量容差下能识别每一个低位故障。div某位使输出低于测量下限时，该位记为失败。

## 跳过与结果

`_should_check=0`、stable保护和下游条件在选择阶段筛除。缺接口或寄存器时打印原因并跳过；原生输入未测到稳定时钟时，报告失败，不写寄存器。每个实际测试的节点打印一条UVM_LOW。

rsp.failed是失败检查次数，rsp.ok只看失败数是否为0。查看汇总中的tested、skipped、checking disabled和stable upstream skipped，不能只看ok。

没有任何功能检查节点时报错。筛选后没有候选且并非全部被显式屏蔽或stable保护时也报错；已经进入插件的节点全部因缺接口跳过，当前实现仍可返回ok。该结果不代表功能已经验证。

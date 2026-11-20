# check_measure

测量当前时钟，不重新配置寄存器。tree 已完成build，接口已经connect。

## 调用

在已有 tree 和 clk_agt 的 task 中：

```systemverilog
clk_tree_check_measure_req req;
clk_tree_check_measure_seq seq;

req = clk_tree_check_measure_req::type_id::create("req");
req.tree = tree;
req.check_duty = 0;
req.skip_nodes.push_back(tree.clk_debug);
seq = clk_tree_check_measure_seq::type_id::create("measure");
seq.req = req;
seq.start(clk_agt.sqr);
if (seq.rsp != null)
    foreach (seq.rsp.failed_nodes[i])
        `uvm_info("CLOCK", seq.rsp.failed_nodes[i].get_name(), UVM_LOW)
```

clk_debug 为示例节点，替换为实际需要跳过的对象。不需要自定义请求时可调用 `clk_agt.sqr.check_measure()`。

## 请求

| 成员 | 默认值 | 含义 |
| --- | --- | --- |
| `tree` | null | 时钟树 |
| `check_observation` | 1 | 启用测量；置0时报错 |
| `check_freq` | 1 | 比较输出频率 |
| `check_duty` | 1 | 检查允许测量占空比的节点 |
| `min_freq_hz` | 0 | 正数覆盖测量下限；0使用settings.min_freq_hz |
| `skip_nodes` | 空队列 | 本次不检查的对象 |

## 测量顺序

1. 从tree.nodes选择允许检查、有vif且声明测量能力的节点，去掉skip_nodes。
2. 按接口合并平均窗口、最大上升沿间隔和所需项目，启动测量。
3. 各接口共同推进。对每个节点先判断是否有时钟，与_resolved_active比较。
4. 有效性通过后，再按请求检查频率和占空比。
5. 记录失败节点；同一接口的全部节点检查完成后才停止它。

关闭check_freq和check_duty，仍然检查有没有时钟。期望关闭的节点只检查活动，不拿0Hz去等待稳定频率。

## 量化时钟

DTO等输出不一定每个周期都相同。节点声明平均窗口和最大上升沿间隔，接口据此安排采样与超时；不会通过放宽最终频率误差来容忍不稳定。

普通测量合并前级量化特性。共享接口取各节点所需窗口和间隔的最大值，避免一个使用者提前清除另一个使用者的结果。

## 结果

rsp.ok表示所选节点全部通过；rsp.failed_nodes保存失败对象，每个节点只出现一次。一个节点失败后继续检查其他节点。

没有可测量节点时报错。频率未稳定、活动状态错误、频率不符和占空比不符分别报告；停止测量后用last_*读取保存结果，不能把last_valid当成稳定通过。

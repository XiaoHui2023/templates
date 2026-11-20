# route_check

检查前级输出到后级输入的RTL连线，不验证器件内部功能。每次只驱动一个前级，避免错误串线被并行激励掩盖。

tree需要build，信号接口需要connect。开始时会执行一次低功耗配置；随后不再写寄存器，只驱动和释放信号。

## 调用

```systemverilog
clk_tree_route_check_req req;
clk_tree_route_check_seq seq;

req = clk_tree_route_check_req::type_id::create("req");
req.tree = tree;
seq = clk_tree_route_check_seq::type_id::create("route");
seq.req = req;
seq.start(clk_agt.sqr);
if (seq.rsp != null)
    `uvm_info("CLOCK", $sformatf("failed %0d", seq.rsp.failed), UVM_LOW)
```

在已有tree和clk_agt的task中执行。请求只有tree，快捷调用为 `clk_agt.sqr.test_route()`。

## 逐路检查

1. 遍历source连接，收集每个前级以及接到它的全部输入端口。
2. 检查前级默认输出和后级输入是否有接口，任一端不允许检查则跳过。
3. 前级输出force为0，等待1ns，比较全部后级输入。
4. force为1，等待1ns，再比较全部后级输入。
5. release前级，继续下一组。

多输入用输入键区分。clk和cell没有内部功能，可以让同一接口充当输入和输出。stable时钟和PLL也参与连线检查。

## 结果

每条被测试连线打印test；跳过时打印缺失端口或屏蔽原因。输入不符累计错误后继续，0、1两次比较可以分别失败。

rsp.failed是失败比较次数，不是失败节点数或连线数。rsp.ok表示已执行比较全部通过。

没有source连线、全部连线跳过或某个前级没有返回有效检查状态时报告fatal。部分跳过但其余通过不等于完整连接覆盖，需要同时查看test和skip日志。

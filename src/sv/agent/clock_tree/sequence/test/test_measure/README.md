# test_measure

设置新目标后，配置寄存器并检查实际时钟。

```systemverilog
clk_agt.sqr.test_measure(.check_freq(1), .check_duty(0));
```

## 请求与步骤

req包含tree，以及check_observation、check_freq、check_duty，三个检查选项默认均为1。check_observation为0时报错；关闭频率和占空比仍检查活动。

1. 检查请求、tree与build状态。
2. 调用tree.configure，按当前目标随机化并配置。
3. 把tree和三个检查选项交给check_measure。
4. 两步都通过后返回rsp.ok=1。

配置失败或测量失败立即终止test。不需要重新配置时，直接使用check_measure。

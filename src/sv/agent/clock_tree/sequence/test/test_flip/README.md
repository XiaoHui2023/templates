# test_flip

启动一次器件功能测试；激励、寄存器遍历和恢复由flip_check执行。

```systemverilog
clk_agt.sqr.test_flip();
```

1. 校验req及tree。
2. 创建flip_check请求，传入tree并启动operation。
3. 将operation的ok和failed原样转交；没有response时按一次失败处理。

req只有tree。rsp.failed是失败检查次数。快捷task在汇总失败后报告fatal；需要读取详细response时直接使用operation。

测试会改变整树配置，局部恢复不等于恢复调用前状态。具体范围见 [flip_check](../../operation/flip_check/README.md)。

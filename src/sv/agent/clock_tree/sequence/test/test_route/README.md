# test_route

启动一次器件间连线测试；信号驱动、采样和释放由route_check执行。

```systemverilog
clk_agt.sqr.test_route();
```

1. 校验req及tree。
2. 创建route_check请求，传入tree并启动operation。
3. 将operation的ok和failed原样转交；没有response时按一次失败处理。

req只有tree。rsp.failed是失败比较次数。快捷task在汇总失败后报告fatal；需要读取response时直接使用operation。

测试开始时会应用低功耗配置，之后观察原生激励或临时探测空闲连线。连线筛选、驱动权限与超时见 [route_check](../../operation/route_check/README.md)。

# agent 与 sequencer

agent 创建一个 kit_sequencer，实例名为 `sqr`。在 agent 的 build_phase 之前，把 tree 放入 config_db；类型使用最高派生 tree，而不是 tree_base。

```systemverilog
uvm_config_db#(clk_tree_tree)::set(this, "clk_agt", "tree", tree);
```

agent 取得 tree 后赋给 `sqr.tree`。以下 task 的 tree 参数省略或为 null 时，都使用这个句柄。

## 调用

```systemverilog
clk_agt.sqr.config_reg();    // 只配置
clk_agt.sqr.check_measure(); // 不重新配置，只测量
clk_agt.sqr.test_measure();  // 配置后测量
clk_agt.sqr.test_flip();     // 器件功能
clk_agt.sqr.test_route();    // 器件间连线
```

按需要选择其中一项，不要求全部连续调用。flip 和 route 会先应用低功耗配置，不能视为保持当前时钟状态的被动检查。

## 测量选项

check_measure 和 test_measure 都接收以下参数，默认值均为 1。

| 参数 | 作用 |
| --- | --- |
| `check_observation` | 启用节点测量；置 0 会终止检查 |
| `check_freq` | 比较频率 |
| `check_duty` | 检查节点允许测量的占空比 |

只检查有没有时钟：

```systemverilog
clk_agt.sqr.check_measure(.check_freq(0), .check_duty(0));
```

频率和占空比都关闭时，活动检查仍执行。需要临时跳过节点或修改最低测量频率时，直接创建 operation 请求。

## 日志与失败

`UVM_LOW` 显示配置、测试对象、跳过原因和汇总，`UVM_HIGH` 显示逐项结果及重复配置跳过，`UVM_DEBUG` 显示等待和接口状态。

快捷 task 在 operation 返回失败后报告 fatal；operation 内可继续的检查错误会先累计，让同一次运行给出全部结果。

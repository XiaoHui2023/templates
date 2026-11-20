# 模型

tree 保存全部节点，并负责绑定和配置。类名都带 `class_prefix`；默认 tree 类型为 `clk_tree_tree`。

## 配置一次时钟

```systemverilog
clk_tree_tree tree;
tree = clk_tree_tree::type_id::create("tree");
tree.build(your_regmodel);

tree.low_power();
tree.clk_cpu.enabled = 1;
tree.clk_cpu.frequence = 24000000;
tree.configure();
```

`build` 完成初次随机化，不写寄存器。`low_power` 只改变关闭偏好。`configure` 按当前目标再次随机化，再执行寄存器配置，需要在 task 中调用。全部节点都没有寄存器时，build 不传寄存器对象。

## 目标与结果

设置 `enabled`、`frequence`、`open`、`sel`、`ratio` 等目标属性，不直接改 `_resolved_*`。后者是求解结果，下一次随机化会重新计算。

clk 和 cell 的 enabled、frequence 构造默认值均为 -1，表示没有显式要求。clk 输入正频率后，Python 会在未指定 enabled 时补 1；显式 enabled 优先。关闭时保留 frequence，再开启可继续使用它。

有前级且未指定开关的 clk 默认软开启；low_power 为 1 时软关闭。显式开启和 stable 不受软偏好覆盖。stable 必须开启；输入 stable 为 true 且未填 enabled 时初始化为 1，显式关闭会在输入阶段报错。

PLL 可通过 SV 的 enabled 指定开关；-1 保持默认求解。关闭 PLL 前要让依赖它的时钟满足关闭或改选输入的要求。low_power 不主动关闭 PLL。

## tree 成员

| 成员或方法 | 含义 |
| --- | --- |
| `nodes` | 全部 node_base 对象的队列，每个输出组各占一项 |
| `<节点名>` | 单输出节点句柄 |
| `<节点名>[string]` | 按输出组名索引的节点句柄 |
| `built` | build 已成功完成 |
| `build(regmodel)` | 绑定、初始化和随机化 |
| `low_power()` | 向节点设置低功耗偏好 |
| `configure()` | 求解并应用当前目标 |
| `require_built(ctx)` | 检查初始化状态，错误中包含调用位置 |

## 公共节点成员

| 成员 | 含义 |
| --- | --- |
| `source`、`sources[string]` | 默认输入或具名输入的前级 |
| `output_name`、`output_peers[string]` | 当前输出组与同一器件的其他输出 |
| `_resolved_active`、`_resolved_freq` | 求解后的活动状态与频率，频率单位 Hz |
| `_should_print` | 打印解析和固定控制等诊断字段，默认 0 |
| `_should_check` | 允许测量、flip和route，默认 1；不改变配置 |

`_should_print` 不隐藏节点对象，也不控制 INFO 日志。route 的任一端关闭检查时，该连线跳过。

接口编译后，节点还持有 `vif`、`in_vif`、`out_vif` 及具名端口数组。纯配置编译不声明这些接口成员。

## 寄存器切片

每个绑定保存 `field`、`offset` 和 `width`。`is_bound()` 判断字段是否连接；同一字段可只绑定部分比特。

写入前真实读取父寄存器，合并控制切片并保留其他位。批量修改同一个父寄存器时合并为一次写回，实际值未变则省略写入。普通读改写只适用于支持的 RW/RO 访问组合，不能套用于 W1C、RC、WO 等有副作用的字段。

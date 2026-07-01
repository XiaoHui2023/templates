# consolver 约束求解

## 外部程序

`pll_mini` 通过 `bin/consolver.exe` 调用 Z3。可执行文件不提交；缺失时直接报错，提示从 `https://github.com/XiaoHui2023/consolver` 下载并放入 `src/c/pll_mini/bin`。

调用形态固定为：

```bash
consolver solve clock_tree.smt2 --format json --timeout-ms <ms>
```

Current Python flow does not create a temporary `clock_tree.smt2`. It passes SMT-LIB text directly and returns JSON text; logs show `consolver solve start: input-text`.

`sat` 返回模型，`unsat` 或 `unknown` 直接失败。失败信息保留命名约束，读者可以从约束名定位到节点、端口和关系。

调试时设置 `settings.debug_consolver_smt_path`。Python 约束层会在调用 consolver 前直接把 SMT-LIB 文本写到该路径，用于查看传给 consolver 的实际约束；即使后续求解返回 `unsat`，该文件也已保存到该路径。不要通过 `.j2` 模板输出 SMT 调试文件，避免求解失败时模板渲染阶段拿不到约束输入。

## 约束文件

整个 clock tree 渲染为一份 SMT-LIB 文件，只调用一次 consolver。每个节点有一个有效性变量，每个输出端口有一个整数频率变量；mux 有 `sel`，div/dto 有 `ratio`。

约束名按节点和作用命名，例如：

- `clk_x__target_freq`
- `mux_a__arm_0__freq`
- `div_b__freq_div`
- `pll_c__pll_freq__out`

## 频率关系

source 和单输出 pll 的 `freq` 是必填频率锚点，直接用于传播；它们本身不是输出频率求解目标。clk 以及其他节点的 `freq` 是可选锚点，填写时才约束输出频率。

锚点只在节点有效时约束输出频率；未被目标使用的分支可以保持无效。多输出 `inno` 没有单一输出 `freq`，由下游目标牵引具体输出组。

gate、cell、inv 只做频率透传。pll_mini 阶段认为 gate 常开，不把 gate 寄存器配置状态放进 SMT。

div/dto 使用整数除法：

```text
f_out = div(f_in, ratio)
```

普通 div 的 `ratio` 下限为 1。dto/dto_n 的 `ratio` 下限为 2，因为 `ratio=1` 无法写成合法 `step`。

## PLL 可实现性

TCI 的整数倍频关系轻量，直接进 SMT：

```text
f_out = f_ref * clkf
```

SC、DW、INNO 不把完整寄存器公式作为非线性大约束塞进 SMT。约束层把 PLL 当作固定频率源，只向下游传播输出频率；PLL 参考频率与寄存器系数在求解后按已定频率计算。

这样做避免 Z3 在全树上处理大面积 `div(* ref fbdiv, * refdiv postdiv...)` 非线性表达式。需要新增 PLL 类型时，先写清候选参考频率，再写求解后的寄存器换算。

## 失败信息

求解失败时不猜原因，只显示：

- consolver 状态：`unsat` 或 `unknown`
- `unknown` 原因
- 相关命名约束

不要吞掉 consolver 输出，也不要只报“求解失败”。失败信息必须能让人继续分析具体节点和约束。

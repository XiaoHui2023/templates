# Python 频率模型

## 节点输入

`pll_mini` 复用 clock tree 的 node 输入。节点名来自顶层 `nodes` 的 key，节点体内不写 `name`。

所有节点都允许 `freq`。省略表示该节点不主动约束频率；填写正整数表示该节点输出频率已确定，可用于传播和约束求解。

`source` 必须填写 `freq`。所有 `pll` 必须填写 `freq`，本身视为已知频率器件，不把输出频率交给 SMT 求解。`inno` 是多输出 PLL，`freq` 可填写 `{"0": hz, "1": hz}` 指定各输出端口；也可填写整数，表示所有输出端口使用同一频率。

节点体允许保留 clock tree 扩展字段；`pll_mini` 只读取本阶段声明过的字段。`enable`、`disable`、`stable` 等 clock tree 字段在 `pll_mini` 中没有实际语义。

## 简单模型

每个节点在 Python 里只保留求解需要的信息：

- 有效性：该节点是否被目标 clk 使用。
- 输出频率：单输出节点为 `out`，多输出 PLL 按输出组区分。
- 选择：mux 的 `sel`。
- 分频：div/dto 的 `ratio`。

这个阶段不写实际寄存器配置，不展开 PLL 具体寄存器公式，不读取 gate open 真实配置。

## 通路语义

source 是固定频率源，必须从 Python 输入给出 `freq`。它只负责向下游传播确定频率，不参与 PLL 寄存器公式求解。

单输出 pll 是固定频率器件，必须从 Python 输入给出 `freq`。约束层只校验它的参考频率可实现性，输出频率直接作为锚点传播。

gate、cell、inv 都是等频透传。gate 默认打开；gate 寄存器只在生成 C 配置时使用。

mux 在约束中选择一路输入。固定 `sel` 时只允许该路；未固定时由 consolver 选择。

clk 没有 `freq` 时不作为目标，不主动牵引上游求解。clk 有正频率时，该频率就是目标约束。

多输出 PLL 的各输出端口频率来自 PLL 节点自身的 `freq` 配置。它们在约束求解前已经确定，会直接进入 SMT 模型；寄存器公式计算也读取这些端口目标频率，不再依赖下游消费者反推。

## 传播与减压

求解前按确定频率做轻量传播：

- 等频节点直接传递频率。
- 固定 ratio 的 div 可以正向或反向确定频率。
- 遇到 mux 时，用目标频率和上游可能频率裁掉明显不可能的分支。
- 分支仍有多种可能时停止传播，交给 consolver 选择。

向后传播遇到未定 ratio 的 div/dto 时停止。向前传播遇到不能唯一确定的 mux 时停止。

## 求解结果

consolver 返回后还原为 `SolveModel`。`TreeResolve` 再按节点生成：

- `active`
- `resolved_freq`
- `port_freqs`
- `ratio`
- `mux_sel`
- `gate_open`
- `pll_cfg`

`pll_cfg` 来自求解后的频率和寄存器公式，不属于 Python 简单频率模型。

# Python 频率模型

## 插件边界

每个节点的输入字段、别名、设置、约束、公式和寄存器规则集中在 `node/plugins/` 中对应的一个 Python 文件。`node/discovery.py` 发现插件，`node/registry.py` 建立输入索引；新增插件不修改公共类型清单。

`node/base.py` 定义接口，`node/behaviors.py` 提供透传和固定源能力，`node/ratio.py` 提供整数比值约束与回放，`node/synthesis.py` 提供参数拟合。公共层使用插件能力，不按节点类型分支。

| 节点 | 插件文件 |
| --- | --- |
| cell | `node/plugins/cell.py` |
| clk | `node/plugins/clk.py` |
| clk_div_with_clken | `node/plugins/clk_div_with_clken.py` |
| div_div | `node/plugins/div_div.py` |
| div_dto | `node/plugins/div_dto.py` |
| div_div_r | `node/plugins/div_div_r.py` |
| gate | `node/plugins/gate.py` |
| inv | `node/plugins/inv.py` |
| inv_cell | `node/plugins/inv_cell.py` |
| inv_mux | `node/plugins/inv_mux.py` |
| mux | `node/plugins/mux.py` |
| pll_dw | `node/plugins/pll_dw.py` |
| pll_inno | `node/plugins/pll_inno.py` |
| pll_sc | `node/plugins/pll_sc.py` |
| pll_tci | `node/plugins/pll_tci.py` |
| source | `node/plugins/source.py` |
| source_pad | `node/plugins/source_pad.py` |

## 执行阶段

1. 输入归一化移除排除节点及其独占空载上游，再校验端口、拓扑和寄存器路径。
2. 公共层声明端口频率和活动状态，插件添加频率关系及无条件参数范围。
3. 求解图后，插件读取自己的状态并拟合器件参数。
4. 插件独立回放公式，寄存器计划合并保留字段并生成配置。

`active` 只决定频率传播，不决定初始化范围。PLL 拟合在图求解后执行，因此图可满足不等于器件参数可实现。

## 共享控制

多个节点绑定同一寄存器字段及比特范围时，插件通过 `control_encodings` 提供编码，公共层约束最终硬件值相等。不同器件的逻辑分频比不必相同；单独使用的字段不额外引入共享编码变量。

`frequency_demand_from_config` 声明频率需求，`terminal_demand_from_config` 声明自身动作需求。归一化缓存需求并用工作队列清理空载上游；显式排除优先于独占控制的动作或初值，原本独立初始化由 `standalone_initialization` 声明。

普通字段按地址从零合并，`extra_regs` 覆盖同字段，只有附加字段的地址排在前面。PLL 的阶段顺序、锁定轮询和字段编码由自己的插件声明，不套用普通数组的一次写入规则。

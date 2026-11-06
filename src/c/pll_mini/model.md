# Python 频率模型

## 输入与插件

输入只使用顶层 `nodes` 和 `extra_regs`，不接受旧 `tree` 层。节点名来自字典键，节点体不能填写 `name`。`null` 或 `exclude: true` 节点不进入图；引用不存在或被排除的节点会报出引用位置。未知字段、插件、输出名、环路和不存在的 mux 输入均在求解前拒绝。

`node/base.py` 定义稳定 hook；`node/discovery.py` 发现本地插件，`node/registry.py` 根据插件声明构建输入索引。每个具体节点的模型、别名、设置、约束、状态解码、公式和寄存器规则集中在 `node/plugins/` 中对应的一个 Python 文件。新增节点只增加插件文件，不修改注册表、图、求解器、验证器或公共模板。

基础能力不包含器件型号：`node/behaviors.py` 提供透传、单输入及固定频率源；`node/ratio.py` 提供整数比值求解和回放；`node/synthesis.py` 提供固定输出目标的拟合流程。`registers/program.py` 按插件给出的槽位、字段表达式和写入阶段生成配置函数及就绪轮询。具体公式、合法范围、字段键、阶段顺序和 C 符号由插件声明。

公共设置只包含生成选项、容差和工具预算。器件设置由插件自己的 Pydantic 模型验证，输入仍可使用扁平 `settings`。公共 `SolveModel` 只保存 `active`、端口频率和不透明的 `node_values`；寄存器规划状态由插件的 `resolved_values` 返回。

## 执行顺序

1. 校验节点、端口、拓扑及寄存器路径。
2. 公共层声明端口和有效性，调用插件建立频率关系。
3. 求解频率图，由插件读取自有变量。
4. 调用插件 `fit`，按确定频率计算器件参数。
5. 调用插件 `verify` 独立回放公式，再生成寄存器计划。

`active` 是求解器的频率传播状态，不决定初始化范围。输入归一化移除 `null`、显式 `exclude: true` 节点及因排除而失去全部消费者的独占上游；共享上游保留。其余节点按插件声明贡献寄存器字段或 PLL 初始化，不因未被时钟引用、mux 未选中或 `active=false` 而裁剪。PLL 的函数、实例、锁定等待和地址宏由完整配置计划派生；gate 固定开启。所有保留的写寄存器参数仍无条件约束合法范围，PLL 不按节点名跳过拟合。详见 [初始化合同](initialization.md)。

普通寄存器从零合并全部配置字段后整字写入，不是按字段保留原值。若因路径筛选删去一个仍属初始化范围的字段，该位会被写零；因此不能把频率路径使用关系当作字段删除依据。`extra_regs` 按既定覆盖规则参与同寄存器合并。没有节点或 `extra_regs` 指定的位仍采用原有零值语义，不新增 mask 或读改写。

source 和 PLL 输出频率是输入锚点。复杂 PLL 系数在图求解后拟合，不把完整非线性硅片公式塞入全树 SMT。图可满足不等于系数一定可实现；拟合失败有独立阶段和诊断文件。

## 共享硬件字段

拓扑引用不等于有效需求。归一化从显式排除及无需求透明叶节点开始，用同一工作队列收缩空载上游。`demand_from_config` 每个节点只计算一次频率需求，再将结果传给插件的 `terminal_demand_from_config(value, frequency=...)`。默认保留独立初始化，透明插件按频率锚点判断，有实际写入的插件保留其独立终端动作。不依赖具体类型名单，也不以 `reg` 字段存在推断写入。

`frequency_demand_from_config` 表示节点自身的频率锚点。`terminal_demand_from_config` 的缓存结果统一保护原始叶节点和收缩后叶节点，包括插件声明的实际初始化动作。`standalone_initialization` 仅保留原本无消费者的独立配置，不保活失去需求的普通分支。可编程 quotient 的 `init_ratio` 与 mux 插件的 `init_sel` 将明确的写入意图纳入自身需求及无条件约束；固定功能 `ratio` / `sel` 保持不写寄存器语义。

插件通过 `control_encodings` 提供控制字段及硬件编码表达式。只有多个节点确实绑定同一寄存器字段及比特范围时，公共层建立编码相等约束；不同插件的逻辑 ratio 不必相等，但最终硬件值必须相等。未被目标使用、仍会写寄存器的节点也遵守该约束。

单独使用的控制字段不额外引入编码变量，避免无关的非线性约束拖慢全树。共享控制变量的额外合法域由所属插件声明。PLL 多阶段配置保持独立，不混入普通 steps 的合并语义。

普通 steps 和 `extra_regs` 按寄存器归并，多字段一次写入；extra-only 寄存器位于数组最前面。数组项仍为地址和值，不增加 mask。`extra_regs` 对同字段保留原有覆盖语义。

## 扩展验证

插件文件名必须与其唯一节点类的 `kind` 默认值相同。输入别名由 `InputForm` 声明，插件内的 `SETTINGS` 声明该文件自己的设置模型。发现阶段拒绝节点所有权不唯一、重复设置字段和歧义输入形式。插件不互相导入，公共层不导入具体插件类。

运行 `python tools/check_plugin_ownership.py` 检查文件所有权、跨插件导入、公共层具体类型选择和模板专有字段引用；注册表也纳入检查。静态检查不能代替真实生成、公式回放和旧版输出对照。新增插件必须覆盖端口、约束、状态、回放及配置贡献。

| 节点 | 唯一插件文件 |
| --- | --- |
| cell | `node/plugins/cell.py` |
| clk（clock） | `node/plugins/clk.py` |
| clk_div_with_clken | `node/plugins/clk_div_with_clken.py` |
| div_div（div、div_n） | `node/plugins/div_div.py` |
| div_dto（dto、dto_n） | `node/plugins/div_dto.py` |
| div_div_r（div_r） | `node/plugins/div_div_r.py` |
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

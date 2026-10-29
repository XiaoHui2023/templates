# clock_tree

## 示例

```yaml
settings:
  class_regmodel: chip_regmodel

nodes:
  osc:
    kind: source
    frequence: 24000000

  gate_cpu:
    kind: gate
    source: osc
    reg: clk_ctrl.cpu_gate
    open: 1

  clk_cpu:
    kind: clk
    source: gate_cpu
    path: dut.clk_cpu
    stable: true
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `settings` | `Settings` | | 全局选项。 |
| `nodes` | `dict[str, Node]` | | 按名字管理的节点。 |

### Settings

节点可独立保存，用 `nodes: !include example_nodes.yaml` 引入。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `clk_tree_` | 类型名前缀。 |
| `class_regmodel` | `str` | `""` | 寄存器模型类型名。 |
| `direct_config` | `bool` | `false` | 生成轻量配置入口。 |
| `min_freq_hz` | `int` | `15000` | 允许最低频率，单位 Hz。 |
| `max_freq_hz` | `int` | `5000000000` | 允许最高频率，单位 Hz。 |
| `active_cycles` | `int` | `1` | 活动判定周期数。 |
| `stable_cycles` | `int` | `3` | 稳定判定周期数。 |
| `period_tolerance` | `float` | `0.02` | 周期相对误差。 |
| `duty_min` | `float` | `48.0` | 占空比下限。 |
| `duty_max` | `float` | `67.0` | 占空比上限。 |
| `duty_tolerance_pct` | `float` | `0.05` | 占空比容差。 |
| `plugin` | `dict[str, dict]` | `{}` | 节点插件的全局选项。 |

`settings.plugin.<作用域>` 由注册插件校验；例如 `settings.plugin.pll_sc.fbdiv_max`。

### 前级引用

| 写法 | 含义 |
| --- | --- |
| `pll_cpu` | 单输出前级。 |
| `pll_cpu[core]` | 多输出节点的 `core` 输出组。 |
| `{ "0": "xtal", "1": "pll_cpu" }` | 按输入端口键指定多个前级。 |

### 寄存器模型路径

| 写法 | 含义 |
| --- | --- |
| `blk.field` | 整个字段。 |
| `blk.field[1]` | 单个比特。 |
| `blk.field[7:0]` | 连续位段。 |

### Node

#### 公共字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `kind` | `str` | | 节点插件名。 |
| `exclude` | `bool` | `false` | 排除该节点，不生成实例、接口和寄存器绑定。 |
| `source` | `str` / `dict[str, str]` | | 前级引用。 |
| `outputs` | `list[str]` | `[]` | 输出组。 |
| `path` | `str` | | 观测路径。 |
| `in_path`、`out_path` | `str` | | 默认输入、输出路径。 |
| `in_paths`、`out_paths` | `dict[str, str]` | `{}` | 具名端口路径。 |
| `reg` | `str` | | 默认寄存器模型路径。 |
| `regs` | `dict[str, str]` | `{}` | 具名寄存器模型路径。 |
| `output_regs` | `dict[str, dict[str, str]]` | `{}` | 按输出组覆盖的寄存器路径。 |
| `output_config` | `dict[str, dict]` | `{}` | 按输出组覆盖的插件配置。 |

#### 插件配置

插件字段与公共字段平级，由对应 Python 插件定义和校验。已注册插件的字段拼错或多写会报错。不再使用 `config` 容器。

| `kind` | 字段 |
| --- | --- |
| `source`、`source_pad` | `frequence` |
| `pll_sc`、`pll_dw`、`pll_inno`、`pll_tci` | `frequence`、`enabled`；`pll_inno` 还支持 `group_id` |
| `clk` | `frequence`、`enabled`、`low_power`、`stable`、`check_duty`、`unfix_frequence`、`unfix_enabled` |
| `cell` | `cell_kind`、`frequence`、`enabled` |
| `gate` | `open`、`unfix_open`、`fix_open`、`fix_close` |
| `mux` | `max_sel`、`sel`、`unfix_sel` |
| `div_div` | `ratio`、`unfix_ratio` |
| `div_div_r`、`div_dto` | `ratio`、`unfix_ratio` |
| `clk_div_with_clken` | `ratio`、`unfix_ratio`，ratio 为 2、3、4 或 6 |
| `inv`、`inv_cell`、`inv_mux` | `inverted`、`fix_inverted` |

`stable: true` 且省略 enabled 时补 1；显式 enabled 小于等于 0 会报错。`exclude: true` 不等于关闭时钟；保留的节点不能引用被排除的节点。

mux 的选择值来自 source 的实际键集合。键使用非负整数的十进制字符串；例如只有 `"2"`、`"5"` 时，只允许选择 2 或 5。省略 max_sel 不增加上限，填写后只缩小该集合。

### mux 切换等待

`settings.plugin.mux`：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `switch_cycles` | `8` | 写 sel 后等待旧、新输入中最慢时钟的周期数。 |
| `switch_timeout_ns` | `1000000` | 等待预算上限，单位 ns；超过则报错，不继续写 sel。 |

切换前临时开启旧、新输入路径上的 gate，等待一个最慢输入周期，再写 sel。切换等待结束后才按目标关闭 gate。选择值未变化时不重复配置或等待。

[切换配置示例](example_config_plan.yaml)保留新输入、最终关闭旧输入；切换期间仍由配置计划保持两端供钟。

周期数须满足目标 mux 的同步延迟；这是时间预算，不是硬件完成确认。输入运行要求由各提供者插件处理，寄存器或锁定条件不足时拒绝配置。

独立 PLL 先编程，再分次检查锁定，硬件锁定时间可以重叠；mux 的写后等待同样不阻塞其它就绪动作。级联参考和共享输入仍按依赖执行，寄存器访问保持串行。详见[配置调度](node/base/config/README.md)。

## 日志

日志由 UVM verbosity 控制：`UVM_LOW` 显示配置、测试点、跳过与汇总；`UVM_HIGH` 显示读回跳过及逐项测量结果；`UVM_DEBUG` 显示等待进度和接口状态。错误不受 INFO verbosity 过滤。

### DTO 配置

`settings.plugin.div_dto` 支持以下选项。

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `reg_high_means_reset` | `false` | 复位高有效。 |
| `reset_on_config` | `false` | 每次配置前复位。 |
| `sync_wait_ns` | `200` | 复位和 load 同步等待时间，单位 ns，大于 0。 |
| `settle_ns` | `200` | flip 测量前的稳定等待时间，单位 ns。 |

1. 需要复位时，断言复位并等待同步。
2. 拉低 load，写 step 和 bypass，释放复位。
3. 等待同步，最后拉高 load。
4. 等待 load 同步后返回。

当前没有同步完成状态输入，sync_wait_ns 应覆盖目标 IP 的同步延迟，不表示读取了硬件完成状态。

### 共享寄存器

绑定同一寄存器字段及相同比特范围的分频节点，实际写入编码必须一致。分频比显式要求互相矛盾时，随机化失败，不会分别配置后相互覆盖。reset 和 load 是控制动作，不用于约束分频比。

### 输出组覆盖

多输出节点用 `output_config` 覆盖指定输出组，未覆盖的字段沿用节点顶层值。

```yaml
nodes:
  pll_audio:
    kind: pll_inno
    outputs: [fast, slow]
    frequence: 480000000
    output_config:
      slow:
        frequence: 240000000
```

### clk_div_with_clken

```yaml
nodes:
  bus_div:
    kind: clk_div_with_clken
    source: osc
    in_path: dut.bus_div_i
    out_paths:
      clk_arm_core: dut.clk_arm_core
      hclk: dut.hclk
      hclken: dut.hclken
    regs:
      div: clk_ctrl.divider[3:0]
      rst: clk_ctrl.reset
      load: clk_ctrl.load
    ratio: 3
```

三个输出名固定，无需填写 outputs。clk_arm_core 直通输入，hclk 和 hclken 共用分频。div 绑定四位字段，rst 和 load 可省略；仅有分频字段时也可使用 reg。全局 `settings.plugin.clk_div_with_clken` 支持 `reg_high_means_reset` 和 `settle_ns`，默认分别为 false 和 200。

| 编码 | 分频比 |
| --- | --- |
| `000x` | 2 |
| `001x` | 3 |
| `01xx` | 4 |
| `1xxx` | 6 |

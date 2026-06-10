# pll_mini

## 示例

```yaml
regmodel:
  - path: blk_pll_sc.pd
    address: 256
    fields:
      - name: vocpd
        lsb: 0
        width: 1
tree:
  name: main
  nodes:
    xtal:
      kind: source
      freq: 24000000
    pll_sc:
      kind: pll
      source: xtal
      pll_kind: sc
      freq: 60000000
      regs:
        lock: blk_pll_sc.stat.lock
        fbdiv: blk_pll_sc.div.fbdiv
    clk_out:
      kind: clk
      source: pll_sc
      freq: 60000000
settings:
  main_fn: chip_pll_config
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `tree` | `Tree` | 必填 | 单棵时钟树；节点字段与 clock_tree 同形，不含 RTL `path` 与仿真度量项。 |
| `regmodel` | `list[Reg]` | 必填 | 寄存器模型。 |
| `settings` | `Settings` | 见下表 | 全局选项。 |

### Settings

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `main_fn` | `str` | `pll_mini_config` | 配置入口 C 函数名。 |
| `header_guard` | `str` | `PLL_MINI_H` | 头文件 include guard。 |
| `reg_write_fn` | `str` | `pll_mini_reg_write` | 寄存器写函数名。 |
| `gate_reg_high_means_open` | `bool` | `false` | 门控寄存器写 1 是否表示打开。 |
| `div_reg_high_means_reset` | `bool` | `false` | div 的 rst 写 1 是否表示复位。 |
| `dto_reg_high_means_reset` | `bool` | `false` | dto 的 rst 写 1 是否表示复位。 |
| `lock_timeout_us` | `int` | `1000` | PLL lock 轮询超时，微秒。 |
| `pll_sc_fbdiv_min` | `int` | `16` | 允许 PLL SC FBDIV 下限。 |
| `pll_sc_fbdiv_max` | `int` | `84` | 允许 PLL SC FBDIV 上限。 |

### Reg

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path` | `str` | 必填 | 寄存器点分路径；点号换为下划线并大写后作 C 宏前缀。 |
| `address` | `int` | 必填 | 寄存器物理地址。 |
| `fields` | `list[Field]` | 必填 | field 列表。 |

### Field

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | field 名。 |
| `lsb` | `int` | 必填 | 最低位索引。 |
| `width` | `int` | 必填 | 位宽。 |

### Tree

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | 必填 | 时钟树名。 |
| `nodes` | `dict[str, Node]` | 必填 | 节点表，键为节点名。 |

须含恰好一个 `kind: clk` 节点，以其 `freq` 锚定活动路径与分频比。

### Node

`kind` 决定节点形状；`regs` 或 `reg` 非空时须能在 `regmodel` 中解析。门控开闭、mux 选择、div/dto 分频比与 PLL 各 field 写入值由 Python 按 clock_tree 同一套频率公式推算，不在 YAML 填写。

| `kind` | 主要字段 | 说明 |
| --- | --- | --- |
| `source` | `freq` | 时钟源频率，单位 Hz。 |
| `pll` | `source`, `pll_kind`, `freq`, `regs` | 目标输出频率；`regs` 键集合与型号一致。 |
| `div` | `source`, `regs` | 分频比由前级频率与 clk 锚定频率推算。 |
| `dto` | `source`, `regs` | 分频比由前级频率与 clk 锚定频率推算。 |
| `gate` | `source`, `reg` | 活动路径上门打开，其余关闭。 |
| `mux` | `source`, `reg` | 选择能到达 clk 的输入标签。 |
| `inv` | `source` | 反相，无寄存器。 |
| `clk` | `source`, `freq` | 输出频率锚点，单位 Hz。 |

配置顺序与 clock_tree **config_reg** 相同：活动 **pll** 写寄存器后 **wait_lock**；活动 **div** 与 **dto**；打开的 **gate**；活动 **mux**；关闭的 **gate**。

生成的 **pll_mini.c** 中每步寄存器写为已合并的整字常量 **reg_word**，并附各 field 切片的 **lsb**、**width**、**value** 注释行供核对。

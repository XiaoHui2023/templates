# Power Up Operation

## 输入字段

| 字段 | 说明 |
| --- | --- |
| `enable_soft_reset` | 是否在 power up 前执行软复位，默认关闭 |
| `freq_divide` | 时钟分频系数 |
| `freq_sel` | 时钟分频参数 |
| `clk_gen_select` | 时钟分频计算方式 |
| `sd_bus_pwr_vdd1` | VDD1 电源使能 |
| `sd_bus_vol_vdd1` | VDD1 电压 |
| `sd_bus_pwr_vdd2` | VDD2 电源使能 |
| `sd_bus_vol_vdd2` | VDD2 电压 |
| `signaling_en` | 1.8V 信号使能 |

## 流程

1. `enable_soft_reset == 1` 时执行 `reset_operation_seq`。
2. 配置电源、内部时钟、卡时钟。
3. 等待内部时钟稳定、卡插入、卡稳定。
4. 配置 eMMC、Host、MSHC、调谐相关控制寄存器。
5. 首次 power up 后等待 `power_up_time_ns`。

## 关键点

- 默认不执行软复位，需要主动打开。
- 当前软复位路径是 CMD 和 DAT 软复位，不是单独写 `SW_RST_ALL`。

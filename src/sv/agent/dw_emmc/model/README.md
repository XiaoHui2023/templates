# Model

## settings

| 成员 | 说明 |
| --- | --- |
| `boot_cfg` | 启动、电压、默认速度、默认位宽、频率配置 |
| `chk_clk_cfg` | 已生成 clock 的期望频率、容差 |
| `vif` | `top/interface.sv` 生成的顶层 virtual interface |
| `regmodel` | RAL 顶层寄存器模型 |
| `has_randomized` | 随机化完成标志 |

约束：`regmodel != null`、`has_randomized == 1`；`post_randomize()` 检查 `vif != null`。

## context

| 成员 | 说明 |
| --- | --- |
| `data_width_cur` | 当前已应用的数据位宽 |
| `bus_speed_mode_cur` | 当前已应用的速度模式 |
| `has_power_up` | 已完成上电流程 |
| `has_initialized` | 已完成 card 初始化流程 |

默认状态：eMMC 为 `data_width_cur == 1`、`bus_speed_mode_cur == LEGACY`；SD/SDIO 为 `data_width_cur == 1`、`bus_speed_mode_cur == DS`。

## 公共声明

| 枚举 | 取值 |
| --- | --- |
| `voltage_e` | `V3_3`、`V3_0`、`V1_8`、`V1_2` |
| `bus_speed_mode_e` | eMMC: `LEGACY`、`HIGH_SPEED_SDR`、`HIGH_SPEED_DDR`、`HS200`、`HS400`; SD: `DS`、`HS`、`SDR12`、`SDR25`、`SDR50`、`SDR104`、`DDR50` |
| `resp_type_select_e` | `NO_RESP`、`RESP_LEN_136`、`RESP_LEN_48`、`RESP_LEN_48B` |
| `multi_blk_sel_e` | `SINGLE`、`MULTI` |
| `auto_cmd_enable_e` | `AUTO_CMD_DISABLED`、`AUTO_CMD12_ENABLED`、`AUTO_CMD23_ENABLED`、`AUTO_CMD_AUTO_SEL` |
| `dma_sel_e` | `SDMA`、`ADMA2`、`ADMA2_3`；仅 `enable_dma: true` 时生成 |
| `uhs_mode_sel_e` | `SDR12/LEGACY`、`SDR25/HIGH_SPEED_SDR`、`SDR50`、`SDR104/HS200`、`DDR50/HIGH_SPEED_DDR`、`UHS2/HS400` |
| `boot_partition_enable_e` | `NO`、`1`、`2`、`USER_AREA` |
| `boot_partition_access_e` | `NO`、`1`、`2`、`RPMB`、`GP1`、`GP2`、`GP3`、`GP4` |

## base_item

| 成员 / 函数 | 说明 |
| --- | --- |
| `set_child_context(child)` | 给子对象设置 sequencer、depth、name，并 reseed |
| `pre_randomize()` / `post_randomize()` | 随机化配对检查；未成对时 `uvm_fatal` |

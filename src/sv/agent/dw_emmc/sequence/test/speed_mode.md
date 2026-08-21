# Speed Mode Test

## 输入

| 字段 | 作用 |
| --- | --- |
| `enable_legacy_1bit/4bit/8bit` | eMMC `LEGACY` 各位宽开关，默认只开 8-bit |
| `enable_high_speed_sdr_1bit/4bit/8bit` | eMMC `HIGH_SPEED_SDR` 各位宽开关，默认只开 8-bit |
| `enable_high_speed_ddr_4bit/8bit` | eMMC `HIGH_SPEED_DDR` 各位宽开关，默认只开 8-bit |
| `enable_hs200_4bit/8bit` | eMMC `HS200` 各位宽开关，默认只开 8-bit |
| `enable_hs400_8bit` | eMMC `HS400` 8-bit 开关，默认打开 |
| `enable_ds_1bit/4bit` | SD/SDIO `DS` 各位宽开关，默认只开 4-bit |
| `enable_hs_1bit/4bit` | SD/SDIO `HS` 各位宽开关，默认只开 4-bit |
| `enable_sdr12_1bit/4bit` | SD/SDIO `SDR12` 各位宽开关，默认只开 4-bit |
| `enable_sdr25_1bit/4bit` | SD/SDIO `SDR25` 各位宽开关，默认只开 4-bit |
| `enable_sdr50_1bit/4bit` | SD/SDIO `SDR50` 各位宽开关，默认只开 4-bit |
| `enable_sdr104_1bit/4bit` | SD/SDIO `SDR104` 各位宽开关，默认只开 4-bit |
| `enable_ddr50_4bit` | SD/SDIO `DDR50` 4-bit 开关，默认打开 |

## Kit 调用

`kit_sequencer.speed_mode_test()` 开放同名开关参数。默认值与 `speed_mode_test_seq` 一致：每种速度只打开最大支持位宽，其他支持位宽默认关闭。

```systemverilog
env.emmc_agent.sqr.speed_mode_test(
    .enable_hs200_4bit(1),
    .enable_hs400_8bit(1)
);
```

## 流程

eMMC 按开关运行 `LEGACY`、`HIGH_SPEED_SDR`、`HIGH_SPEED_DDR`、`HS200`、`HS400` 支持的位宽组合。

SD/SDIO 按电压和能力位选择 `DS`、`HS`、`SDR12`、`SDR25`、`SDR50`、`DDR50`、`SDR104`，再按各速度的位宽开关运行。

每个速度点都调用 `rw_test_seq`，固定执行单块写再单块读，并由 `rw_test_seq` 完成初始化、切总线和 scoreboard 比较。

## 关键点

- 该测试是速度模式覆盖测试，不随机选择读写路径。
- 每个速度点都执行同一类多块写读主路径，避免不同速度点覆盖面不一致。
- 默认每种速度只打开最大数据位宽；其他支持位宽默认关闭，但可以单独打开。
- scoreboard 比较由 `rw_test_seq` 内部完成。

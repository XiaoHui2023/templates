# Speed Mode Test

## 输入

无独立输入字段。测试根据 `settings.boot_cfg` 中的电压、能力位和默认读写配置运行。

## 流程

eMMC 依次运行 8-bit 下的 `LEGACY`、`HIGH_SPEED_SDR`、`HIGH_SPEED_DDR`、`HS200`、`HS400` 读写测试。

SD 按电压和能力位选择 DS、HS、SDR12、SDR25、DDR50、SDR50、SDR104。

每个速度点都调用 `rw_test_seq`，固定执行多块写再多块读，并由 `rw_test_seq` 完成初始化、切总线和 scoreboard 比较。

# connection

做信号连线检查。

## 特性

- 检查连线两端的值是否一致。
- 检查连线响应是否超时。
- 检查无源变化。
- 只改变驱动强度的事件会被忽略。
- 报错包含实例路径。

## Python 输入

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `class_prefix` | `connection_` | 生成符号前缀。 |
| `default_data_width` | `1` | `DW` 默认值。 |
| `default_latency` | `5.0` | `LATENCY` 默认值。 |
| `time_unit` | `1ns` | `timeunit`。 |
| `time_precision` | `1ps` | `timeprecision`。 |
| `check_enable_default` | `true` | `check_enable` 初始值。 |

## SV parameter

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `DW` | `default_data_width` | 信号位宽。 |
| `LATENCY` | `default_latency` | 允许延迟。 |
| `CHECK_ENABLE_DEFAULT` | `check_enable_default` | `check_enable` 初始值。 |

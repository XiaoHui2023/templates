# connection

做信号连线检查。

## 覆盖场景

- 检查连线两端的值是否一致。
- 检查连线响应是否超时。
- 检查无源变化。
- 只改变驱动强度的事件会被忽略。
- 报错包含实例路径。

## 生成配置

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `class_prefix` | `Connection` | 生成符号前缀，使用大驼峰。 |
| `default_data_width` | `1` | `DW` 默认值。 |
| `default_latency` | `5.0` | `LATENCY` 默认值。 |
| `time_unit` | `1ns` | `timeunit`。 |
| `time_precision` | `1ps` | `timeprecision`。 |
| `check_enable_default` | `false` | `check_enable` 初始值。 |

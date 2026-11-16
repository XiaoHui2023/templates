# AXI monitor

## 示例

```yaml
class_prefix: axi_
protocol: AXI4
data_width: 64
addr_width: 32
id_width: 4
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `axi_` | 类型名前缀。 |
| `protocol` | `AXI3` / `AXI4` / `AXI4_LITE` | `AXI4` | AXI 协议版本。 |
| `data_width` | `32` / `64` / `128` / `256` / `512` / `1024` | `64` | 数据位宽。AXI4-Lite 只允许 32 或 64。 |
| `addr_width` | `int` | `32` | 地址位宽，范围 1～64。 |
| `id_width` | `int` | `4` | 事务 ID 位宽，范围 1～32。 |

# General scoreboard

## 示例

```yaml
class_prefix: general_
mode: address
reuse_read_expectations: false
require_golden: true
require_match: true
atomize: true
monitor_policy: drop
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `general_` | 类型名前缀，建议以下划线结尾。 |
| `mode` | `str` | `address` | `address` 按地址匹配，`ordered` 按输入顺序匹配，`set` 按多重集合匹配。 |
| `reuse_read_expectations` | `bool` | `false` | 本轮读期望可重复使用，写期望逐个消费。 |
| `require_golden` | `bool` | `true` | 要求本轮至少收到一包合法 golden 输入。 |
| `require_match` | `bool` | `true` | 要求本轮至少成功匹配一个比较单元。 |
| `atomize` | `bool` | `true` | 按有效字节比较；为假时整包比较。 |
| `match_address` | `bool` | `true` | 将地址作为匹配条件。 |
| `match_command` | `bool` | `false` | 将读写命令作为匹配条件。 |
| `compare_address` | `bool` | `true` | 比较地址。 |
| `compare_command` | `bool` | `true` | 比较读写命令。 |
| `compare_data` | `bool` | `true` | 比较有效字节的数据。 |
| `compare_response` | `bool` | `false` | 比较响应状态。 |
| `monitor_policy` | `str` | `drop` | `drop` 丢弃尚无 golden 匹配条件的数据，`buffer` 保存至结束并忽略无关残留，`strict` 保存并检查全部残留。 |
| `max_pending` | `int` | `65536` | 每个输入方向实际保留的比较单元数量上限，包含已覆盖的读模型。 |
| `max_keys` | `int` | `1048576` | 一次复位期间可登记的 golden 匹配条件数量上限。 |
| `max_payload_bytes` | `int` | `1048576` | 单个输入包的有效数据字节数上限。 |

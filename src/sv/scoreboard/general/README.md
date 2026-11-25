# General scoreboard

## 示例

```yaml
class_prefix: general_
mode: state
reuse_read_expectations: false
expected_units: -1
require_golden: true
require_match: true
atomize: true
monitor_policy: buffer
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | `str` | `general_` | 类型名前缀，建议以下划线结尾。 |
| `mode` | `str` | `address` | `address` 按地址匹配，`ordered` 按输入顺序匹配，`set` 按多重集合匹配，`state` 按有效字节地址比较写入终态。 |
| `reuse_read_expectations` | `bool` | `false` | 事务模式中读期望可重复使用，写期望逐个消费；state 不支持读复用。 |
| `expected_units` | `int` | `-1` | 预期比较单元数，-1 按本轮期望义务数推导；state 为独立有效字节地址数，其余为 golden 单元数。 |
| `require_golden` | `bool` | `true` | 未显式设置预期单元数时，要求至少收到一包合法 golden。 |
| `require_match` | `bool` | `true` | 未显式设置预期单元数时，要求至少成功匹配一个比较单元。 |
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

终态写入场景使用 `mode: state`、`atomize: true`、`match_address: true`、`reuse_read_expectations: false`。推荐 `monitor_policy: buffer`，允许 monitor 先到；省略 mode 时模型默认 address；随库示例显式选择 state。详见 [使用说明](scoreboard.md)。

# uvm_gp_adapter

## 示例

```yaml
class_name: packet_gp_adapter
item_type: gp_example_types::packet_t
data:
  member: words
  kind: queue
  element_bits: 16
  byte_order: big
address:
  encode: item.addr
  decode: item.addr = gp.get_address();
command:
  encode: "item.is_write ? UVM_TLM_WRITE_COMMAND : UVM_TLM_READ_COMMAND"
  decode: item.is_write = gp.is_write();
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_name` | `str` | `uvm_gp_adapter` | 组件类名。 |
| `item_type` | `str` | | 用户数据类型，可含包名、类名及类型参数。 |
| `item_is_class` | `bool` | `false` | 用户类型是否为类。 |
| `create_item` | `str` | `new()` | 解码时创建对象的表达式，可使用工厂。 |
| `data` | `BufferMapping` | | 数据缓冲区映射。 |
| `byte_enable` | `optional BufferMapping` | | 字节使能映射，省略表示无字节使能。 |
| `address` | `ScalarMapping` | | 地址映射，省略时编码为零。 |
| `command` | `ScalarMapping` | | 命令映射，省略时编码为写命令。 |
| `response_status` | `ScalarMapping` | | 响应映射，省略时编码为未完成。 |
| `streaming_width` | `ScalarMapping` | | 每拍字节数映射，省略时使用有效数据长度。 |
| `data_length` | `optional ScalarMapping` | | 有效字节数映射，省略时使用编码缓冲区长度。 |
| `max_bytes` | `int` | `1048576` | 每段编码缓冲区及 GP 有效字节数的上限。 |
| `encode_hook` | `str` | `return 1;` | 编码后的自定义函数体。 |
| `decode_hook` | `str` | `return 1;` | 解码后的自定义函数体。 |

### ScalarMapping

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `encode` | `str` | | SV 表达式，读取 `item`，也可读取当前 `gp`。 |
| `decode` | `str` | `""` | SV 语句，读取 `gp` 并写入 `item`。 |

表达式按目标 GP 字段的位宽和枚举类型转换。窄字段、符号扩展、地址单位换算和命令编码由表达式明确指定。省略 `decode` 表示不恢复该字段。

### BufferMapping

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `member` | `str` | `data` | `item` 中的成员路径，可写 `header.words` 或 `lanes[0]`。 |
| `kind` | `str` | `queue` | `packed`、`fixed`、`dynamic`、`queue`。 |
| `element_bits` | `int` | `8` | 每元素位数，包含实际存储的全部比特。 |
| `byte_order` | `str` | `little` | 元素内低字节优先或高字节优先，分别为 `little`、`big`。 |
| `count` | `optional str` | | 编码元素数表达式，省略时取成员容量，packed 取一个元素。 |
| `pack_body` | `optional str` | | 自定义编码函数体，与 `unpack_body` 成对填写。 |
| `unpack_body` | `optional str` | | 自定义解码函数体，与 `pack_body` 成对填写。 |

数组索引从零开始，packed 向量低位为 bit 0。非整字节元素扩为完整字节，最高字节的多余比特补零。解码按有效字节数计算元素数，定长数组要求容量完全匹配，动态数组和队列按元素数调整大小。`count` 小于源容量时仅编码前面的元素。

`data_length` 选择编码后的有效字节前缀，解码只恢复该前缀。它的单位是字节，`count` 的单位是元素。

字节使能映射保留 `00` 和 `ff` 字节，支持周期性重复的短掩码，不会删除禁用的数据字节。

### 自定义转换

`pack_body` 读取 `item`，将结果写入 `bit [7:0] bytes[$]`。`unpack_body` 读取该字节队列并写入 `item`。两者返回 `1` 表示成功，返回 `fail("原因")` 表示失败。自定义函数体负责自己的位宽、容量和格式检查；`member`、`kind`、`count`、`element_bits`、`byte_order` 不参与自定义函数体的处理。

`encode_hook` 读取 `item` 并修改新建的 `gp`，可设置扩展对象及 DMI。`decode_hook` 读取 `gp` 并修改新建的 `item`。函数体的局部变量写在语句之前，成功时返回 `1`。

例如将非整字节头字段与动态数据拼成一段缓冲区：

```yaml
data:
  pack_body: |
    bytes.push_back({item.opcode, item.address[12:8]});
    bytes.push_back(item.address[7:0]);
    foreach (item.payload[i]) bytes.push_back(item.payload[i]);
    return 1;
  unpack_body: |
    if (bytes.size() < 2) return fail("short header");
    item.opcode = bytes[0][7:5];
    item.address = {bytes[0][4:0], bytes[1]};
    item.payload.delete();
    for (int i = 2; i < bytes.size(); i++) item.payload.push_back(bytes[i]);
    return 1;
```

任意布局、多层对象、关联数组、压缩、校验和与私有扩展使用自定义函数体。无法从类型名字自动推断这些格式。

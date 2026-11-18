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
  member: addr
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
| `streaming_width` | `LengthMapping` | | 每拍字节数映射，省略时使用有效数据长度。 |
| `data_length` | `optional LengthMapping` | | 有效数据长度，省略时使用编码缓冲区长度。 |
| `byte_enable_length` | `optional LengthMapping` | | 字节使能有效长度，省略时使用编码掩码长度。 |
| `constants` | `list[ConstantField]` | `[]` | 长度、地址和字段表达式使用的常量。 |
| `allowed_commands` | `list[str]` | `[read, write, ignore]` | 允许的命令，可选择 `read`、`write`、`ignore`。 |
| `address_bits` | `int` | `64` | 地址有效位数，编码与解码均拒绝越界地址。 |
| `byte_enable_policy` | `str` | `preserve` | 字节使能策略。 |
| `require_streaming_width` | `bool` | `true` | 读写命令要求非零每拍字节数，设为假可接受表示连续地址的零值。 |
| `max_bytes` | `int` | `1048576` | 每段编码缓冲区及 GP 有效字节数的上限。 |
| `encode_hook` | `str` | `return 1;` | 编码后的自定义函数体。 |
| `decode_hook` | `str` | `return 1;` | 解码后的自定义函数体。 |

### ScalarMapping

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `encode` | `optional str` | | SV 表达式，读取 `item`，也可读取当前 `gp`。 |
| `decode` | `str` | `""` | SV 语句，读取 `gp` 并写入 `item`。 |
| `member` | `optional str` | | 双向成员路径，省去普通赋值语句。 |
| `constant` | `optional int or str` | | 编码常量值或SV表达式。 |

`constant`、`encode`、`member` 按顺序选择编码来源，前两者互斥。`member` 自动恢复 GP 字段，也可与 `constant` 组合；`decode` 与 `member` 二选一。两者均省略表示不恢复该字段。命令成员使用 `uvm_tlm_command_e`，响应成员使用 `uvm_tlm_response_status_e`；其他枚举编码可通过表达式明确转换。

### LengthMapping

包含 ScalarMapping 的来源与目标字段，并增加长度单位。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `unit` | `str` | `bytes` | `bytes` 表示字节，`elements` 表示对应缓冲区元素个数；每拍长度以数据元素为单位。 |

元素个数按每元素的完整编码字节数换算。负长度、超出可表示范围或无法整除的解码元素数均被拒绝。

### ConstantField

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | `str` | | 表达式中引用的常量名。 |
| `type` | `str` | `int` | SV类型，可指定打包位宽。 |
| `value` | `int or str` | | 数值或SV表达式。 |

### BufferMapping

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `member` | `str` | `data` | `item` 中的成员路径，可写 `header.words` 或 `lanes[0]`。 |
| `kind` | `str` | `queue` | `packed`、`fixed`、`dynamic`、`queue`。 |
| `element_bits` | `int` | `8` | 每元素位数，包含实际存储的全部比特。 |
| `byte_order` | `str` | `little` | 元素内低字节优先或高字节优先，分别为 `little`、`big`。 |
| `count` | `optional str` | | 编码元素数表达式，省略时取成员容量，packed 取一个元素。 |
| `decode_count` | `optional str` | | 解码元素数表达式，省略时使用有效缓冲区长度，可读取 `bytes` 与已恢复的 `item` 字段。 |
| `encoding` | `str` | `raw` | 字节编码，`bit_enable` 将每个比特扩为一个 `00` 或 `ff` 字节，仅用于字节使能。 |
| `fields` | `list[PackedField]` | `[]` | packed 数据的比特布局。 |
| `pack_body` | `optional str` | | 自定义编码函数体，与 `unpack_body` 成对填写。 |
| `unpack_body` | `optional str` | | 自定义解码函数体，与 `pack_body` 成对填写。 |

数组索引从零开始，packed 向量低位为 bit 0。非整字节元素扩为完整字节，最高字节的多余比特补零。解码按有效字节数计算元素数，定长数组要求容量完全匹配，动态数组和队列按元素数调整大小。`count` 小于源容量时仅编码前面的元素。

`data_length` 选择编码后的有效字节前缀，解码只恢复该前缀。它的单位是字节，`count` 的单位是元素。

字节使能映射保留 `00` 和 `ff` 字节，支持周期性重复的短掩码，不会删除禁用的数据字节。

### PackedField

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `member` | `optional str` | | `item` 成员路径，解码时恢复到该成员。 |
| `constant` | `optional int or str` | | 编码常量或表达式，解码时检查相等。 |
| `lsb` | `int` | | 字段最低比特的位置。 |
| `width` | `int` | | 字段位数。 |

`fields` 与自定义函数体、元素个数表达式互斥，字段之间不能重叠。编码选择常量或成员值，未使用的比特补零，解码拒绝这些位置的非零数据。目标成员无法保存字段值时拒绝转换。`byte_order` 控制完整 packed 数据的字节顺序。普通容器映射与字段布局都采用从零开始的比特位置。

```yaml
constants:
  - {name: MAGIC, type: "bit [7:0]", value: 165}
data:
  kind: packed
  byte_order: big
  fields:
    - {lsb: 0, width: 13, member: address}
    - {lsb: 13, width: 3, member: opcode}
    - {lsb: 16, width: 8, constant: MAGIC}
```

### 字节使能策略

| 取值 | 含义 |
| --- | --- |
| `preserve` | 使用配置的掩码，支持周期性短掩码；无映射时编码为空掩码。 |
| `disabled` | 禁用掩码，拒绝带有效掩码的GP。 |
| `all_enabled` | 全部数据字节有效，拒绝包含禁用字节的GP。 |
| `required` | 非空数据要求有效掩码，可使用周期性短掩码。 |
| `full_length` | 掩码有效长度与数据有效长度相同。 |

`disabled`、`all_enabled` 不配置掩码映射；`required`、`full_length` 配置 `byte_enable`。`bit_enable` 按每元素的低位到高位扩展，`byte_order: big` 则反向排列。

```yaml
address_bits: 16
allowed_commands: [read, write]
address: {member: address}
command: {member: command}
data: {member: words, kind: queue, element_bits: 16, byte_order: big}
data_length: {member: count, unit: elements}
streaming_width: {member: beat_elements, unit: elements}
byte_enable_policy: full_length
byte_enable: {member: strobes, kind: packed, element_bits: 4, encoding: bit_enable}
```

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

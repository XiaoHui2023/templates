# ral_test

适用于已建立 RAL 并打通总线访问的环境，按配置依次启动寄存器自测 sequence；`reset` 与 `access` 为仅前门的自实现检查，其余开关仍使用 UVM 内建 sequence。

## 示例

```yaml
class_prefix: ral_test_
access: true
block_access: false
```

## 数据结构

### Models

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| class_prefix | string | ral_test_ | 生成类型名前缀；主 sequence 为此前缀加 seq |
| reset | bool | false | 寄存器复位默认值自测 |
| access | bool | false | 寄存器前门写读自测；按 field 翻转可写位、比对后立刻写回测前读到的整寄存器值，再测下一个 field |
| block_access | bool | false | block 级前门连通性自测；每个 block 在其直接下属寄存器中任意一个通过即可，每个寄存器任意一个 field 通过即可 |
| mem_hdl_paths | bool | false | 启用 uvm_reg_mem_hdl_paths_seq |
| bit_bash | bool | false | 启用 uvm_reg_bit_bash_seq |
| ignore_partial_ro_fields | bool | false | 为真时，对仍含可写字段的寄存器，在 map 上为 RO field 设置 NO_FIELD_TESTS；reset 与 access 自测均不比对被标记 field，且 access 仅翻转 RW 位 |

至少启用 reset、access、block_access、mem_hdl_paths、bit_bash 之一。

# cfggen

## 示例

```yaml
ralf_file: example.ralf
class_prefix: cfg_
emit_ral_sync_methods: true
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ralf_file` | `str` | 必填 | 顶层 RALF 文件路径。 |
| `include_dirs` | `list[str]` | `[]` | `source` 语句的附加搜索目录，按顶层 RALF 所在目录解析相对路径。 |
| `encoding` | `str` | `utf-8` | RALF 文件的文本编码。 |
| `class_prefix` | `str` | `cfg_` | 配置类名称前缀。 |
| `base_class` | `str` | `uvm_sequence_item` | block 与 system 配置类的共同基类。 |
| `ignored_field_accesses` | `list[str]` | `[ro]` | 忽略的 field 访问方式。 |
| `emit_ral_sync_methods` | `bool` | `false` | 是否提供寄存器模型值同步方法。 |
| `value_name` | `str` | `value` | reg 类的组合值成员名。 |
| `rand_mode_lock_name` | `str` | `rand_mode_locked` | reg 类的组合值随机锁成员名。 |
| `reset_value_name` | `str` | `reset_value` | reg 类的复位参数名。 |
| `constraint_name` | `str` | `_cst` | field 与组合值的等式约束名。 |
| `set_ral_method_name` | `str` | `set_ral_value` | 向寄存器模型复制值的方法名。 |
| `get_ral_method_name` | `str` | `get_ral_value` | 从寄存器模型读取值的方法名。 |

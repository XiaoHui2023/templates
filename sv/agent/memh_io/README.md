# memh_io

本族提供可读写 memh 文件的 UVM agent：用 64 位字节地址保存 8 位数据，没写过的地址不算有数据。
多数场景只需配置 `class_prefix` 作为类名前缀，默认 **`memh_io_`**，建议含末尾下划线以便与固定后缀拼接；写出 memh 行宽等其它项按需设置。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_ap` | input | `uvm_tlm_generic_payload` | 输入 payload 按地址与数据写入 memory，不区分 command |
| `o_load_ap` | output | `uvm_tlm_generic_payload` | 输出 memh 文件加载产生的 payload |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `settings` | `<prefix>settings` | 可选，行为设置对象 |
| `init_file` | `string` | 非空时：在 `start_of_simulation_phase` 自动 `load_file` 初始化 memory |
| `dump_file` | `string` | 非空时：在 `final_phase` 自动调用 `save_file`，将当前 memory 保存到该路径 |
| `compare_file` | `string` | 非空时：在 `check_phase` 读取该 memh 并与 memory 比对，与同名成员函数行为一致 |

# 相关文档

- [Sequencer 对外接口](docs/api.md)
- [回调](docs/callback.md)
- [同包全局 function 参考](docs/memh_global_functions.md)

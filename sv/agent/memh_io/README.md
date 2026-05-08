# memh_io

生成一个可读写 memh 文件的 UVM agent：用 64 位字节地址保存 8 位数据，没写过的地址不算有数据。
多数场景只需配置 `class_prefix`（生成类型名前缀）；写出 memh 行宽等其它项按需设置。

# 使用方式

推荐在环境中保存 `agent.sqr`，把 sequencer 当作 memh 访问句柄使用。

- 测试或 scoreboard 可直接调用 sequencer API 读写 memory、加载文件或执行比较。

# ports

| port | 方向 | 类型 | 说明 |
| --- | --- | --- | --- |
| `i_ap` | input | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 输入 payload 按地址与数据写入 memory（不区分 command） |
| `o_load_ap` | output | `uvm_analysis_port #(uvm_tlm_generic_payload)` | 输出 memh 文件加载产生的 payload |

# config_db

| key | 类型 | 说明 |
| --- | --- | --- |
| `init_file` | `string` | 非空时：在 `start_of_simulation_phase` 自动 `load_file` 初始化 memory |
| `dump_file` | `string` | 非空时：在 `final_phase` 自动调用 `save_file`，将当前 memory 保存到该路径 |
| `compare_file` | `string` | 非空时：在 `check_phase` 读取该 memh 并与 memory 比对（与同名成员函数行为一致） |

# API 参考

- **Sequencer（推荐主句柄）**：[docs/memh_io_api.md](docs/memh_io_api.md) — 只写方法名，前缀在文首说明一次。
- **同包全局 function**：[docs/memh_global_functions.md](docs/memh_global_functions.md) — 读/写 memh、与文件比较等，不经过 sequencer 时可用。

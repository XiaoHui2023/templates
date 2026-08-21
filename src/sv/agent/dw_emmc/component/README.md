# Component

## Agent

| 句柄 | 说明 |
| --- | --- |
| `agent.sqr` | `kit_sequencer`，启动 operation、flow、test |
| `agent.scb` | scoreboard，加载 memory 文件和显式检查 |
| `agent.settings` | 配置对象，持有 `vif`、`regmodel`、启动配置、clock 检查配置 |

```systemverilog
env.emmc_agent.scb.load_memh("card_init.memh");
env.emmc_agent.sqr.initial_card();
// env.emmc_agent.sqr.power_up_operation(1); // 主动执行 power up 软复位
env.emmc_agent.sqr.switch_bus(HS400, 8);
env.emmc_agent.sqr.rw_test(.addr(0), .count(2));
env.emmc_agent.sqr.speed_mode_test(.enable_hs200_4bit(1), .enable_hs400_8bit(1));
```

sequence 内只依赖基础 `sequencer`，不 `$cast` 到 kit。

## Kit Sequencer

`kit_sequencer` 只放启动 sequence 的快捷入口，不保存业务状态。

| 层次 | 入口 |
| --- | --- |
| operation | `frequence_set_operation()`、`power_up_operation()`、`reset_operation()`、`cpu_read_bytes()`、`cpu_write_bytes()` |
| flow | `initial_card()`、`switch_bus()`、`send_ext_csd()`、`tune_phase()` |
| test | `rw_test()`、`reg_test()`、`speed_mode_test()`、eMMC `tune_test(data_width = 8)`、`check_clock_frequence_test()` |

## Scoreboard

`agent` 创建 `scb`，并把句柄写入 `sqr.scoreboard`。sequence 通过 `p_sequencer.scoreboard` 上报数据；用户直接通过 `agent.scb` 加载初始镜像或做显式检查。

| 事件 | scoreboard 行为 |
| --- | --- |
| 初始文件加载 | `scoreboard.load_memh()` 或 `scoreboard.load_hex()` 初始化 mirror |
| 写传输完成 | `write_expected_payload(payload)` 更新 expected memory |
| 读传输完成 | `compare_actual_payload(payload)` 与 expected memory 比较 |

sequence 从 `p_sequencer.scoreboard` 发送 `uvm_tlm_generic_payload`。scoreboard 只处理地址、字节和文件加载。不放寄存器配置、命令发送、PIO/DMA 搬运策略。kit sequencer 不提供 scoreboard 快捷函数。

Python 配置 `enable_dma: true` 后才生成 DMA 搬运字段和 kit `rw_test(..., use_dma)` 参数。mobile_storage 默认 `use_dma = 1`，mshc 默认 `use_dma = 0`。

## Callback

外部环境依赖挂在基础 `sequencer` 的 callback 上。

| callback task | 用途 |
| --- | --- |
| `set_frequence(frequence)` | 调用 testbench/时钟环境设置输入时钟 |
| `cpu_read(addr, data, path)` | 按 `path` 读取 32-bit word |
| `cpu_write(addr, data, path)` | 按 `path` 写入 32-bit word |

`path` 使用 `UVM_FRONTDOOR` 或 `UVM_BACKDOOR`。kit 手动 CPU 访问默认前门；启用 DMA 后，DMA buffer 和 ADMA descriptor 访问使用后门以提高效率。

callback 只接收必要数据，不传 sequencer 句柄或 handled 标记。

`frequence_set_operation_seq` 和 `cpu_config_operation_seq` 只负责收集参数、拆装 byte/word、触发 callback。它们不是外部依赖注入点。

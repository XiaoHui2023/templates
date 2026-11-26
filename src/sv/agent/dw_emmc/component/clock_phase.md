# 外部时钟调相

```systemverilog
Emmc_ctrl_clock_phase_types::result_t result;

agent.sqr.set_clock_phase_adapter(project_adapter);
agent.sqr.calibrate_clock_phases(result, 256, 2, 10000, 1000);
```

完成卡初始化并切到目标速度、位宽后，在控制器空闲时调用。未注册适配器时返回 `PHASE_SKIPPED`，原有读写与 CMD21 tuning 不会自动调相。调相期间不要并发提交读写、换频或复位。

## 项目适配器

继承 `Emmc_ctrl_clock_phase_adapter`，按当前速度和位宽返回可调时钟。档位编号从 0 开始，按物理相位顺序排列；寄存器的地址、编码、写入顺序由项目决定。

| 方法 | 作用 |
| --- | --- |
| `describe` | 声明时钟名、分组、档位数和首尾是否相邻。相互影响的时钟放在同一组；组按首次出现顺序处理。 |
| `capture` | 从硬件读取当前档位向量。数组顺序与 `describe` 相同。 |
| `apply` | 应用整组档位并等待稳定；失败时返回 `ok=0`。扫描和回退都调用此方法。 |
| `probe` | 检查当前组。普通坏档返回 `PROBE_REJECTED` 并清理本次传输；不能恢复时返回 `PROBE_FAILED`。组号 `CONFIRM_ALL_GROUPS` 用于验证最终组合。 |

不要用遇到 CRC 错或超时就报 `UVM_FATAL` 的现有读写测试当试跑。适配器应为单次操作设超时；若全局超时中断操作，下一次 `apply` 必须能恢复控制器和原档。

## 搜索和结果

各组分别扫描，组内测试全部档位组合。沿相邻档位移动，已生效的相同向量不重复写。比如一个 8 档时钟和一个 16 档时钟，互不影响时扫描 24 次；相互影响时扫描 128 次。

按到最近失败档或非环绕边缘的距离选裕量最大的通过档；同分优先靠近原档。各组都选好后验证整组配置。默认最多试跑 256 次（含 2 次最终验证），扫描限时 10 ms，回退限时 1 ms。

`PHASE_PASSED` 保留选中档，`result.selected` 按声明顺序返回。超过预算时不写寄存器；坏档之外的失败、无通过档、最终验证失败或超时，会尝试恢复原档。回退失败单独返回 `PHASE_RESTORE_FAILED`，可从 `failure_before_restore` 查看原始原因。

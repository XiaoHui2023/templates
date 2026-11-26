# 外部时钟调相

```systemverilog
uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(agent.sqr, project_callback);
agent.sqr.rw_test();
```

项目在启动传输前注册一次。已经注册了 CPU 或时钟回调的项目，在同一个派生类里补充调相方法。原有读写和测试调用不变。没有回调启用调相、关闭 `agent.settings.clock_phase_auto_enable` 或不支持当前工作点时，沿用原流程。

## 项目回调

在 `Emmc_ctrl_callback` 的派生类中重写 `clock_phase_enabled` 并返回 1，再实现档位说明、读回、写入和探测。一个序列器只允许一个回调启用调相。档位从 0 开始，按物理相位顺序排列；寄存器地址、编码和写入顺序由项目决定。

| 方法 | 作用 |
| --- | --- |
| `clock_phase_accepts`、`clock_phase_select` | 可选。前者判断是否支持工作点；切速完成后，后者选择试跑方式和寄存器。 |
| `clock_phase_describe` | 声明时钟名、分组、档位数和首尾是否相邻。相互影响的时钟放在同一组。 |
| `clock_phase_capture` | 从硬件读取当前档位，数组顺序与分组说明一致。 |
| `clock_phase_apply` | 应用档位并等待稳定；失败时返回 `ok=0`。扫描和回退都调用此方法。 |
| `clock_phase_probe` | 检查当前组。普通坏档返回 `PROBE_REJECTED` 并清理传输；不能恢复时返回 `PROBE_FAILED`。组号 `CONFIRM_ALL_GROUPS` 用于验证最终组合。 |
| `clock_phase_revision` | 可选。项目配置变化时返回新版本，使缓存失效。 |

eMMC HS200 在 1.8 V 或 1.2 V 使用 CMD21 比对固定训练数据，4 位为 64 字节，8 位为 128 字节。启用 HS400 调相时先在 8 位 HS200 训练，再切到 HS400 验证实际数据传输；读 DAT_STROBE 和写时钟可按项目分组，不能用 HS400 下的 CMD21 代替。写试跑只使用保留块。

试跑根据协议完成状态、CRC 和数据结果决定好坏；遇到坏档先恢复到可执行下一档的状态。不要把遇错即终止的普通读写测试当试跑，也不要让试跑重新进入总线切换。整体超时只防回调无响应；如果试跑被中断，下一次 `clock_phase_apply` 必须能恢复控制器和原档。

## 搜索和结果

各组分别扫描，组内测试全部档位组合。沿相邻档位移动，已生效的相同向量不重复写。比如一个 8 档时钟和一个 16 档时钟，互不影响时扫描 24 次；相互影响时扫描 128 次。

按到最近失败档或非环绕边缘的距离选裕量最大的通过档；同分优先靠近原档。各组都选好后验证组合。工作点没变且读回的档位一致时，不重发切换命令，也不重扫。复位、重新初始化、更换回调或项目版本变化会清除缓存。

搜索预算由 `clock_phase_max_probes` 和 `clock_phase_confirm_samples` 控制，默认每工作点 256 次试跑（含 2 次联合验证）。`clock_phase_scan_timeout_us` 和 `clock_phase_restore_timeout_us` 默认分别为 10000 和 1000。

超预算不写相位寄存器；无通过档或试跑故障时尝试回退，报告失败原因，不继续在未通过的工作点传输。启用调相后，同一控制器的总线配置不会插入正在执行的调相。测试环境仍需串行安排同一控制器的数据传输、手动调相和复位，并在空闲时更换回调或修改调相配置。

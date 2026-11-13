# JTAG API

## 扫描

`interface` 负责 TCK、TMS、TDI、TRST 与 TDO 采样。所有扫描低位先传，完成后进入 Run-Test/Idle，TCK 停在低电平。

| 入口 | 行为 |
| --- | --- |
| `scan(is_ir, tx_data, len, rx_data)` | 扫描 IR 或 DR，返回同步移出的 TDO |
| `transfer(addr, tx_data, len, rx_data)` | 原子执行 IR 指令和 DR 扫描 |
| `read(addr, len, rdata)` | 按 read_fill 发送 TDI，返回 DR |
| `write(addr, data, len)` | 写 DR，丢弃同步移出的 TDO |
| `reset_tap()` | 执行配置的复位并进入 Idle |

数据容量为 IR 与 DR 容量中的较大值，未扫描的返回高位清零。扫描中的 X/Z 保留在返回值中。TDO 在 TCK 上升沿之前采样，与上升沿采样的器件输入保留建立时间。

`scan_bits`、`cycle`、`reset_bits`、`run_idle`、`set_instruction` 是扫描内部步骤。并发访问使用持有互斥锁的公开入口。外部电路改变 TAP 状态后，应调用 `reset_tap()`。

## UVM 请求

`register_req` 使用 `addr` 指定 IR 指令，`len` 指定本次扫描位数，`value` 始终表示 TDI 发送数据。`READ` 和 `WRITE` 都执行一次 IR 加 DR 扫描，`SCAN_IR` 和 `SCAN_DR` 仅扫描选中的寄存器。

`register_rsp.value` 始终是实际 TDO，`len` 为本次扫描位数。写响应同样返回 TDO。

```systemverilog
request = jtag_ctrl_register_req::type_id::create("request");
request.configure(p_sequencer.cfg.get_register("status"));
start_item(request);
finish_item(request);
get_response(rsp);
```

`configure` 复制指令、长度、发送值、期望值及掩码，并检查读写权限。第二个参数为 1 时选择写操作。直接构造请求可用于任意原始扫描。

`register_test_seq` 遍历所有可读配置，以四态比较检查掩码指定的位。发送值与期望值分别保存。未配置寄存器时不做扫描；仅写寄存器由显式写请求执行。

## 环境配置

通过 `uvm_config_db#(configuration)` 的 `cfg` 提供配置，通过 `uvm_config_db#(virtual interface)` 的 `vif` 提供接口。既可提前给 `cfg.vif` 赋值，也可独立设置 `vif`。

生成配置作为运行期初值。运行期可修改 `cfg.registers` 和时序字段；修改时序后在扫描空闲时调用 `cfg.apply()`，改变 TAP 状态或复位极性时随后调用 `cfg.vif.reset_tap()`。`cfg.ir_length` 可在生成的 IR 容量内调整。

## 迁移

| 原用法 | 当前用法 |
| --- | --- |
| `vif.logic_if` | `vif`，扫描状态由同一接口保存 |
| `cfg.idcode/public_id/password` | `cfg.registers[name].expected/value` |
| `bits`、`bytes` | `len`，单位为 bit |
| `is_read`、`is_write` | `act_type` |
| 写响应回显发送值 | 写响应返回 TDO |
| 手工维护 `all.f` | 使用配置生成的 `all.f` |

IDCODE、public ID、password 的便捷请求类型保留，使用前要配置同名寄存器。默认仅配置 IDCODE，且不检查其值。

原始扫描也可传入整条链拼接后的 IR/DR 向量；多 TAP 的顺序、其它 TAP 的 BYPASS 位及目标数据切片由使用者安排。

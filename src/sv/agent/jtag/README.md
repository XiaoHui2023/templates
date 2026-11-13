# JTAG

## 示例

```yaml
ir_width: 5
dr_width: 256
tck_period_ns: 100
registers:
  idcode:
    instruction: 0x01
    length: 32
    expected: 0x12345001
    check_mask: 0x0fffffff
  status:
    instruction: 0x02
    length: 13
    access: read_write
    value: 0x123
```

## 数据结构

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `class_prefix` | str | `jtag_ctrl_` | 类型名前缀 |
| `ir_width` | int | 8 | IR 容量，1～4096 位 |
| `dr_width` | int | 256 | DR 容量，1～4096 位 |
| `tck_period_ns` | float | 100 | TCK 周期，至少 0.002 ns |
| `idle_cycles` | int | 0 | 每次 IR 或 DR 扫描后增加的空闲周期 |
| `use_trst` | bool | true | 复位时驱动 TRST |
| `trst_active_low` | bool | true | TRST 低电平有效 |
| `trst_pulse_ns` | float | 100 | TRST 有效时间，至少 0.001 ns |
| `reset_cycles` | int | 5 | TMS 连续为 1 的周期数，至少 5 拍 |
| `connect_settle_ns` | float | 10 | 连线检查电平稳定时间，至少 0.001 ns |
| `read_fill` | 0 或 1 | 0 | 接口直接读操作的 TDI 默认电平 |
| `registers` | dict[str, Register] | `idcode: {}` | 按名字填写寄存器；填写 `{}` 表示无预设寄存器 |

### Register

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `instruction` | int | 0 | IR 指令值 |
| `length` | int | 32 | DR 位数，可以不是整字节 |
| `access` | str | read | 读写权限 |
| `value` | int | 0 | 扫描时从 TDI 发送的值 |
| `expected` | int | 0 | TDO 期望值 |
| `check_mask` | int | 0 | 置 1 的位参与比较 |

| access | 权限 |
| --- | --- |
| `read` | 读 |
| `write` | 写 |
| `read_write` | 读和写 |

指令值应在 IR 容量内。寄存器长度应在 DR 容量内，发送值、期望值和掩码应在寄存器长度内。

IDCODE 指令值由器件决定，默认 0 沿用原配置。检查掩码为 0 时只扫描，不判断设备身份。忽略版本号可填写 `0x0fffffff`。

password、public_id 和其它设备寄存器均按同一结构填写。

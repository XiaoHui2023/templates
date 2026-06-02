# 数据传输

设计路径：
`power_dn->mac->mac_pie`

## 关键词

| 信号名 | 说明 |
| --- | --- |
| `txtstate` | `txrx_state` |
| `fifo_pop` | `tx_fifo_pop` |
| `tx_pop` | `tx_data` |
| `fill_push` | `fill_push` |
| `ext_d_push` | `ext_d_push` |
| `txt_data` | `tx_data` |
| `rxstate` | `rxstate` |
| `fifo_wr` | `curp` |

## 状态

| 值 | 状态名 | 中文含义 | 说明 |
| --- | --- | --- | --- |
| 0x0 | **IDLE** | 空闲 | 等待总线状态，等待下一次主机事务 |
| 0x1 | **SEND_SPLIT** | 发送 SPLIT 包 | 分离式事务 SPLIT，按协议传输 |
| 0x2 | **STSRT** | 发送事务 | 发送令牌/数据包 |
| 0x3 | **TXD_CRC5** | 发送 CRC5 | 令牌包 CRC5 |
| 0x4 | **TXCDATA** | 发送数据 | 数据包内容输出 |
| 0x5 | **NAKIT_PKT** | 等待接收包 | 设备响应握手包 |
| 0x6 | **RXACT_ERR** | 接收错误 | 接收错误处理 |
| 0x7 | **RECV_DATA** | 接收数据 | 接收主机数据包 |
| 0x8 | **SEND_RESP** | 发送握手包 | 发送 ACK/NAK/STALL 等握手响应 |
| 0x9 | **SEND_EOP** | 发送 EOP | End of Packet，事务结束 |
| 0xa | **SEND_DATA** | 发送数据 | 正在发送数据内容 |
| 0xb | **WAIT_XFER** | 等待传输 | 等待传输完成或下一状态 |
| 0xc | **CHK_CRC16** | 检查 CRC16 | 检查接收数据包 CRC16 是否正确 |
| 0xd | **WAIT_DATA** | 等待数据 | 等待下一段数据/响应 |
| 0xe | **TXTTDOUT** | 超时 | 响应超时 |
| 0xf | **WAIT_SUBSLOT** | 等待子时隙 | 高速分离事务等待 |
| 0x10 | **WAIT_TURNAROUND** | 等待 turnaround | 等待收发方向切换 |
| 0x11 | **DATA_TO_STS** | 数据转状态阶段 | 从数据阶段进入状态阶段 |

## 符号

总线：`power_dn->xcsr`

| 信号 | 解释 |
| --- | --- |
| `eptype` | ep1~ep14的类型，每个占用2bit |
| `charpen` | ep1~ep14的使能，每个端口占1bit |
| `curp` | 当前使用的中断空间编号 |
| `DIEPDMAM` | DMA使能 |
| `diepktcnt` | 可用的包，表示包的个数 |
| `diexfersize` | 用于DMA，表示包长度 |

## 寄存器

### IN

| 寄存器 | 作用 |
| --- | --- |
| `DIEPDMAM` | DMA地址 |
| `DIEPTSIZn` | `[0:0]` 表示包长度；`[20:19]` 表示包的个数 |

## UVM

`phy` 与 `mac` 通过 `interface` 的信号交互。

与状态相关的信号：`mac->xpi` 的 `tx_state` 信号。

## 关键信号

```systemverilog
DW_USB_OTG_inst.U_DWC_USB_OTG_core.U_DWC_USB_OTG_power_dn.U_DWC_USB_OTG_mac.U_DWC_USB_OTG_mac.xpi
```

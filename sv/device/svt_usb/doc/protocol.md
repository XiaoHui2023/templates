# 协议

- 设备端 `dut` 和 `vip` 通过 `phy` 连接
- 设备端的每个端口：`dp1s` 和 `dm1s`
- 三态控制由 `OE` 控制，比如 `OE` high 时表示 `dut` 驱动 `DEV_IDLE`，否则无法驱动 `pullup`。

## UVM信号

正常传输时，通常观察 `unit_int` 信号；如果协议栈控制异常，也可在对应的端口处确认。

| 信号名 | 说明 |
| --- | --- |
| `utmi_txvld` | 发送有效 |
| `utmi_txready` | 发送就绪 |
| `utmi_dataout` | 发送数据 |
| `utmi_rxvalid` | 接收有效 |
| `utmi_datain` | 接收数据 |

## 控制信号

| 命令作用 | 传输通路 |
| --- | --- |
| 主机发送数据 | 1字节或2字节 |

路径参考：
`DWC_otg_inst.U_DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_mac.word_if`

## PID结构

**PID [Packet ID]** 第一半包与第二半包互补，用于识别类型。

| 位域 | 含义 | 位数 |
| --- | --- | --- |
| PID[3:0] | 类型码（Type Code） | 4位 |
| PID[7:4] | 类型码反码（Complement） | 4位 |

### PID类型

| PID 类型 | PID 名称 | PID[3:0] | 值 | 类型 | 描述 |
| --- | --- | --- | --- | --- | --- |
| 令牌 | OUT | 0001 | 0xE1 | 地址+端点号，主机向设备发数据 |
| 令牌 | IN | 1001 | 0x69 | 地址+端点号，设备向主机回传数据 |
| 令牌 | SOF | 0101 | 0xA5 | 帧起始标记 |
| 令牌 | SETUP | 1101 | 0x2D | 控制传输开始，主机向设备发送请求 |
| 数据 | DATA0 | 0011 | 0xC3 | 数据PID0 |
| 数据 | DATA1 | 1011 | 0x4B | 数据PID1 |
| 数据 | DATA2 | 0111 | 0x87 | 高速/等时使用 |
| 数据 | MDATA | 1111 | 0x0F | 高速分离事务使用 |
| 握手 | ACK | 0010 | 0xD2 | 接收端确认收到 |
| 握手 | NAK | 1010 | 0x5A | 接收端暂时不能响应或没有数据 |
| 握手 | STALL | 1110 | 0x1E | 端点停止响应，控制端点请求不支持 |
| 握手 | NYET | 0110 | 0x96 | 接收者尚未准备好 |
| 特殊 | PRE/ERR | 1100 | 0x3C | PRE：低速前导；ERR：错误响应 |
| 特殊 | SPLIT | 1000 | 0x78 | 分离事务 |
| 特殊 | PING | 0100 | 0xB4 | 高速主机探测端点 |

## PID原始格式

Field 后是打包结果，从低位开始传输。

```text
PID | addr | endpoint | crc5
```

## SETUP 包请求结构体

SETUP 的 DATA 固定 8 字节。

| 字段 | 子字段 | 长度 | 说明 |
| --- | --- | --- | --- |
| bmRequestType | bit[7] | 1 | 请求方向 |
| bmRequestType | bit[6:5] | 2 | 请求类型 |
| bmRequestType | bit[4:0] | 5 | 请求对象 |

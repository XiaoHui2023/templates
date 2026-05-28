# 设备状态

## 逻辑描述

具体状态和DesignWare IP生成的信号对应变化

```
DUT:
DW_USB_OTG_inst.U_DWC_USB_OTG_core.U_DWC_USB_OTG_power_dn.U_DWC_USB_OTG_mac.U_DWC_USB_OTG_mac.dssr.dssr_state
```

## 状态码

| 值 | 状态名 | 中文含义 | 说明 |
| --- | --- | --- | --- |
| 0x0 | **DEV_INIT** | 设备初始化 | 初始化阶段，配置不够，接口未被复位 |
| 0x1 | **DEV_IDLE** | 空闲状态 | 设备处于空闲，等待主机发起包或控制包 |
| 0x2 | **PULLUP_EN** | 上拉使能 | 端口 D+ 或 D- 上拉使能，开始向主机声明设备连接 |
| 0x3 | **CONNECT** | 连接状态 | 上拉完成，设备检测到连接，等待总线复位 |
| 0x4 | **SEND_CHIRP_K** | 发送 Chirp K | 高速协商流程，设备发送 Chirp K 响应从机请求 |
| 0x5 | **WAIT_HST_CHIRP** | 等待主机 Chirp | 等待主机返回高速握手信号，确认高速模式 |
| 0x6 | **SUSPENDED** | 挂起 | 设备进入挂起或低功耗状态 |
| 0x7 | **RESUMING** | 恢复中 | 从挂起状态恢复，准备重新通信 |
| 0x8 | **HSL_RESET** | 高速复位 | 接收到主机高速复位，执行初始化操作 |
| 0x9 | **HSPLINE_PULSING** | HS 线脉冲 | 线信号 D+ 或 D- 检测过程 |
| 0xa | **PULSING_DONE** | 脉冲完成 | 高速检测中线脉冲结束，准备进入下一状态 |
| 0xb | **DEV_CHIRP_RESET** | 设备 Chirp 复位 | Chirp 后复位，确认速度 |
| 0xc | **DEV_CHIRP_DONE** | Chirp 完成 | 高速握手完成 |
| 0xd | **REMOTE_WAKEUP** | 远程唤醒 | 设备发起远程唤醒 |
| 0xe | **REMOTE_POWER** | 远程电源管理 | 主机远程唤醒/电源状态处理 |
| 0xf | **APP_CFGRD** | 配置读取 | 应用侧配置读取，数据处理完成 |

## 跳转说明

### INIT

- `DEV_INIT` -> `DEV_IDLE` 进入空闲状态

### chirp

- `HS_SND_CHIRP` 拉上了
  - `DEV_CHIRP_END`
  - `WAIT_HST_CHIRP` 处于，失败则保持hs

### PLL RESET 计数

- `DEV_INIT` 退出到连接，计数，进入IDLE状态

### APP

- `SUSPENDED` 进入挂起阶段，退出了

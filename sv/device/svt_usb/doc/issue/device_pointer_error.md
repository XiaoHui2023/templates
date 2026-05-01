# 问题描述

device 指针出错了一个。

## 关键信号

### SRAM

```systemverilog
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.Txf_rf_addr_min[11:0]
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rdp_ptr[11:0]

DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rd_packet_end
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rewind_ptr[11:0]
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rewind_ptr[11:0]
```

## 复位下是一周期

```systemverilog
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rd_packet_end
```

## 取前一个时钟的数据

```systemverilog
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.U_DWC_otg_pktfifof1.rewind_ptr[11:0]
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.txf_rf_end_int[15:0]
```

## 状态

```systemverilog
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_pfc.s2hRd_txf_rdnun[3:0]
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_csr.txfnum_pfc[3:0]
```

## 使能信号

```systemverilog
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_mac.U_DWC_otg_mac_pie.it_ep_info[6:0] + 4
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_mac.U_DWC_otg_mac_pie.in_tkn = 1
DWC_otg_core.U_DWC_otg_power_dn.U_DWC_otg_mac.U_DWC_otg_mac_pie.tkn_pid[3:0] = 1
```

## FIFO/TX数据

重点观察端口上传tx和rx数据线，发现下一个数据很奇怪，错位的情况不同的下一个包会影响一拍。

## 结论

其实在一个数据包结束就处理了。

是前一个命令没结束，下个命令又来了。需要检查device vip，不要马上执行下个动作，必须要至少有一点点间隔。

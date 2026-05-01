# FAQ

## 时间单位错误

仿真时间时序异常，比如 `INIT` 持续时间太久，`send_chirp_k` 错误，`fullt_check` 也有可能与实际时间不符。

需要检查 `svt` 的 `svt_usb` 配置中的月分辨率 `timescale`，必须保持一致。

## suspend超时

超时路径：
`DW_USB_OTG_inst.U_DWC_USB_OTG_core.U_DWC_USB_OTG_power_dn.U_DWC_USB_OTG_mac.U_DWC_USB_OTG_mach.dssr.suspend_3ms`

调用 `scaledown_mode` 后，这个时间被大大缩短，不能一条不停。

触发超时时为什么一定不能发送包或者消息。

## full speed 连接阶段检查顺序

full speed连接完成后，传输就会置于等待状态。

连接需要等待大约3~4us，中间不能有传输，否则就会卡住。

等待方法是加延迟等一小段时间。

## 发送set_address出错

可能device还没起来，需要等久一点，或者检查device时钟异常。

## 发送set_configuration的下一个传输延迟

可能 `set_configuration` 失败。

需要检查 `value` 正确。

## host SPEED_HIGH 切到 otg device没反应

打开 device 仿真，查看芯片识别为高低速设备、断路还是usb协议失败（无反应）。

## otg device 复位流程

1. IDLE[1]
2. DEV_CHIRP_END[4]
3. WAIT_HST_CHIRP[5]
4. FLS_RESET[8]

## device发送错误，完成第一个数据了怎么办

device 发送阶段需要等待下一拍，并且用于每一次发送的阶段。

host 需要等待一点，等device的filor中数据到了再进行传输。

## 发送SETUP之后的DATA包无ACK

发送 SETUP之后ACK，传输阶段收到DATA一直是NACK。

1. 检查 `doepctl0` 的 `[31]EPena` 是否打开

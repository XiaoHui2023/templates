# dw_spi DMA 启动修复

- status: done
- 目标：修正 DMA 写 opcode 字节序，并让 DMA 读在选择 CS 前满足 TX FIFO 启动门槛。
- 完成证据：internal/external DMA 渲染通过，生成代码顺序检查通过，SV 静态检查通过。

# dw_spi DMA 启动修复

- status: done
- created: 2026-08-18 10:00 +08:00
- updated: 2026-08-18 11:17 +08:00
- scene: dw_spi DMA 启动修复

## 范围

- 修正 `SPIDR.SPI_INST` 单字节 opcode 的 16 位容器字节序。
- DMA 读在选择 CS 前向 `DR` 写入指令、地址控制项，并满足 `TXFTLR+1` 启动门槛。
- 同步寄存器、DMA 流程、族设计记录，并验证 internal/external DMA 展开结果。

## 当前状态

- 已定位 `register_config_builder.sv.j2` 的 opcode 拼接方向错误。
- 已定位 `transfer/op.sv.j2` 的 DMA 读分支直接选择 CS，缺少 TX FIFO 预填。
- 已建立项目目标与本轮工作记录，五件套检查通过。
- 已修改 opcode 拼接方向，并在 internal/external DMA 读分支选择 CS 前增加 TX FIFO 控制项预填。
- 已同步寄存器、DMA 流程、族设计记录、项目决议和用户根 DesignWare SPI 参考。
- 已完成实现与文档 diff 自检，旧的高字节 opcode 说明已删除。
- internal DMA 与 external DMA 均已渲染成功；空行、SV 保留字、形参方向、预填顺序和 opcode 拼接检查通过。
- 初次完成时工作区含其它任务改动，提交隔离检查暂时阻止上传。
- stop hook 提示记录新鲜度不足后重新执行五件套检查，结果为 PASS；记录与 INDEX 已再次同步。
- 自动上传前已完成 fetch、远程进度和暂存区审查；5 个 dw_spi 文件范围准确，无上传阻断项。
- 功能提交 `799585b6` 已推送到 `origin/main`。
- 项目 goal、record 和 INDEX 已纳入独立元数据提交范围。

## 验收

- internal DMA 与 external DMA 配置均通过 `jinja_build`。
- 生成的 SV 中 `SPI_INST` 为 `{8'h00, opcode}`。
- DMA 读在 `activate_transfer_cs` 前调用 TX FIFO 控制项预填。
- SV 保留字、参数方向、空行和五件套检查通过。

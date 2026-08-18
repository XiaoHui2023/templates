# flip 串行化记录

- status: done
- created: 2026-08-18 09:20 +08:00
- updated: 2026-08-18 09:42 +08:00
- scene: flip 串行化

## 当前状态

- 用户报告 flip 并行测试时写寄存器可能卡死。
- 已定位批次内 fork/join_none 与共享 semaphore 调度。
- 已完成仓库五件套 Skill 初始化并通过清单检查。
- 已删除 flip 的冲突分批、fork 和显式 semaphore，body 改为逐器件同步测试。
- 已同步 operation 流程、串行寄存器设计和示例注释。
- 已同步 clock_tree 族设计记录和 changelog，并归档批内并行废案。
- 门禁期间修复了并行任务新增的 dw_spi 工作记录元数据格式，未改其任务内容。
- 静态检查确认 flip 模板已无批次、fork、显式 semaphore 或并行任务文案。
- example.yaml 已成功生成完整 clock_tree 输出；生成的 flip operation 同样无并行调度痕迹。
- 空行扫描和本轮 flip 文件的 SystemVerilog 检查通过。
- 全量模板/生成物比对发现旧的 `model/spec.sv` 残留，待清理输出目录后重跑。
- 已隔离旧渲染目录，准备从空输出重新生成。
- 空输出目录重新生成成功。
- 旧渲染目录已移出工作区，当前输出只包含本次全新生成文件。
- 模板与生成物路径一致，空行、flip SV、串行调度和 sequence 分层检查通过。
- flip 不新增模型计算；删除 O(n²) 冲突分批、动态结果数组和并发进程创建。
- 当前环境未运行商业 UVM 仿真器，运行时寄存器总线验证留给集成仿真。

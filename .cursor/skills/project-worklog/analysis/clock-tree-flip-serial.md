# flip 串行调度分析

- status: done
- created: 2026-08-18 09:20 +08:00
- updated: 2026-08-18 09:42 +08:00
- scene: flip 串行化

## 事实

- 当前 operation 先划分无结构冲突批次，再在批次内并行调用 `verify_subject`。
- 每个 worker 在多个寄存器写入点分别获取共享 semaphore，激励与测量发生在锁外。
- 单个器件测试可能多次取得寄存器锁，线程会在配置、激励、等待和再次配置之间交错。

## 结论

- semaphore 只能串行化单次临界区，不能保证一个器件的完整测试事务不与另一器件交错。
- 严格串行应删除批次调度、fork 和共享 semaphore，由 body 逐项同步调用 `verify_subject`。
- 各 `verify_*` 内部的寄存器访问无需再次加锁；保留锁会增加无收益的阻塞点。

## 验证

- 各器件配置调用保持原顺序；`body()` 只负责顺序调度。
- 每个 `verify_*` 仍完成输入释放，普通错误继续累计到最终 response。
- 生成物无 `fork`、批次、显式 semaphore 或 test 层直接信号访问。
- jinja_build、模板/生成物路径、空行和本轮 SV 静态检查通过。

## 实现

- `body()` 按候选队列顺序同步调用 `verify_subject`。
- 删除批次构造、fork、结果数组和显式寄存器 semaphore。
- 各器件检查保留原配置、激励、测量和释放顺序。

# base_seq

为派生 sequence 提供统一类型和 clock_tree sequencer 声明，不执行具体操作。

## 流程

1. 构造 sequence 对象。
2. 由派生 sequence 实现请求处理和执行流程。

## 设计

**base_seq** 没有 req、rsp 或 `body()`，不能作为测试入口。寄存器和 interface 操作分别由具体 operation 承担，test 只编排 operation。

# base_seq

为派生 sequence 提供统一的参数化 REQ/RSP 基类和公共类型，不执行具体操作。

## 流程

1. 派生 sequence 指定 REQ/RSP 类型。
2. 派生 sequence 声明 sequencer 并实现执行流程。

## 设计

**base_seq** 没有 req、rsp 或 `body()`，不能作为测试入口。寄存器和 interface 操作分别由具体 operation 承担，test 只编排 operation。

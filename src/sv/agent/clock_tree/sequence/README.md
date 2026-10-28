# base_seq

为派生 sequence 提供统一的参数化 REQ/RSP 基类和公共类型，不执行具体操作。

派生 sequence 指定 REQ/RSP 类型、声明 sequencer 并实现执行流程。test 负责请求转交和结果合并，operation 负责检查调度；节点插件通过 API 完成各自的配置和功能检查。

# test_freq

- **config_reg** 后 **check_freq**
- 至少一处 **path**，且 **class_regmodel** 非空并有节点绑定 **reg** 或 **regs**

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 减少 **UVM** 日志 |

## 主流程

![](../../../images/test_freq_flow.drawio.svg)

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 子步骤全部通过 |

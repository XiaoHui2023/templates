# test_flip

- 固定 **gate** / **mux**，对每个已绑 **reg** 的 **div** / **dto** 将 **fix_ratio** 写到 **field** 最高有效位分频比，**config_reg** 后 **check_freq**
- 同时存在带 **path** 与带 **reg** 的节点，且 **class_regmodel** 非空

## req

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **tree** | **tree_base** | 时钟树 |
| **quiet** | **bit** | 减少 **UVM** 日志 |

## 主流程

![](flow.drawio.svg)

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部探测对象通过 |

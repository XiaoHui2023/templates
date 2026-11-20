# 版本记录

## 当前设计

输入由settings和nodes组成，节点属性平铺在节点中。exclude只决定是否生成，不表示时钟开关。

Python与SV节点插件分别显式登记。tree通过基础接口完成配置，sequence按能力选择检查；节点差异不写进公共调度。

low_power独立于configure。配置使用动作依赖和临时运行需求，不再按器件类型设置数值优先级。完整验证使用all.f，纯配置可选config.f。

## 历史

| 版本 | 变化 |
| --- | --- |
| v1 | 基线提交9166cab3，使用settings与nodes |
| v2 | 引入Python/SV节点插件，曾允许扁平输入 |
| v3 | 曾只允许扁平输入 |
| v4 | 配置统一到tree.configure；low_power曾作为参数 |
| v5 | SV插件改为显式文件清单，未知类型留给编译检查 |
| v6 | 恢复nodes分组，使用exclude；配置改为动作计划，low_power改为独立调用 |

历史接口不代表当前仍然支持。版本只作文字记录，不对整个templates仓库创建tag。

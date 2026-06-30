# test_route

沿 **gate**、**mux**、**div**、**dto** 等带寄存器的节点做结构探测：对每个 subject 枚举自身控制量取值组合，再与路径上其它节点的组合做笛卡尔积，每次写寄存器后跑 **check_measure**。

## req

| 成员 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| **tree** | **tree_base** | | 待测时钟树 |
| **quiet** | **bit** | `0` | 为真时压缩日志 |
| **debug** | **bit** | `0` | 为真时 **check_measure** 打印等待进度 |

## 流程要点

### 不参与测试的节点

YAML 将 **clk** 节点的 **stable** 设为真时，该时钟为锚定点：**enabled** 与 **frequence** 由 trees 锁定，**low_power** 不关断。

**test_route** 初始化在首次 **config_reg** 之后，沿各 **stable** **clk** 当前 **source** 选通链向上收集 **gate**、**mux**、**div**、**pll**，这些节点不参与 subject 探测；路径上 **pll** 也不参与改频策略，控制量与分频比在探测前固定。落在上述路径上的 subject 直接跳过。

树中存在 **stable** **clk** 时，其余 **clk** 的 **enabled** 在探测阶段保持可随机，避免把锚定路径关断。

若某轮 **config_reg** 后 **stable** **clk** 的 **_resolved_active** 为假，该 subject 或 line combo 跳过。

## rsp

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| **ok** | **bit** | 全部未跳过组合通过 |

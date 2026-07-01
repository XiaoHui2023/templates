# example 目录

提交前跑 **example\check.bat**：族根 **example.yaml** 都要通过 **jinja_build** 生成成功并以 0 退出。

**example.yaml** 是标准回归入口，已经合并原 normal 与压力场景，覆盖：

| 场景 | 用途 |
| --- | --- |
| 基础 kind | source / pll / div / inv / mux / gate / cell / clk 至少一条可解路径 |
| ref_dto | PLL 参考路径上 mux / dto / div 组合 |
| ref_mux | 多层参考 mux 与 inno 参考路径 |
| mux_combo | 四层 mux 组合枚举剪枝压力 |
| deep_div | 同一子树内多路并行 div 求解 |
| div_share | 多个 clk 共享同一 div ratio |
| dual_path | PLL 路径与 xtal 路径汇入 mux |

## 其它样例

| 文件 | 用途 |
| --- | --- |
| `normal.yaml` | 轻量健全检查；保留作人工定位用，不作为提交必跑入口。 |
| `extreme.yaml` | 历史压力样例；压力内容已经并入族根 `example.yaml`。 |
| `unsat.yaml` | 故意无解拓扑，验收诊断输出。 |
| `reg_bit_range.yaml` | 寄存器位宽越界报错。 |
| `reg_missing_field.yaml` | 缺少寄存器 field 报错。 |

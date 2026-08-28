# RALF 配置类设计

cfggen 将顶层 RALF 描述转换为一个 SystemVerilog 文件。每个 reg、block 与 system 分别形成配置类，原有实例关系通过类成员保留。

## 处理流程

1. 读取顶层 RALF，并递归展开 `source` 文件。
2. 收集 block 与 system 定义，解析定义和实例之间的引用。
3. 按访问方式过滤 field，并删除不再包含 field 的 reg。
4. 计算 reg 的有效位宽、复位值和 field 映射。
5. 检查未解析引用、循环依赖、重名与位段重叠。
6. 按依赖顺序输出全部 reg，再输出 block，最后输出 system。

RALF 的原始名称统一转为小写 SystemVerilog 标识符。无法直接使用的字符替换为下划线，保留字增加尾部下划线。所有配置类名称增加 `class_prefix`。

## 类命名

| 对象 | 配置类 | ralgen 类型 |
| --- | --- | --- |
| reg | `class_prefix + block名 + _ + reg名` | `ral_reg_ + block名 + _ + reg名` |
| block | `class_prefix + block名` | `ral_block_ + block名` |
| system | `class_prefix + system名` | `ral_sys_ + system名` |

ralgen 类型采用常见生成命名。接入带定制命名规则的 ralgen 输出时，需要先核对实际类型名。

## reg 类

reg 类固定继承 `uvm_sequence_item`。

| 成员 | 形式 | 规则 |
| --- | --- | --- |
| 组合值 | `rand bit` | 位宽覆盖保留 field 的最低位至最高位，并归一化到零起始。 |
| field | `rand bit` | 每个保留 field 对应一个同名成员，位宽归一化到零起始。 |
| 随机锁 | `bit` | 置位后，`pre_randomize` 关闭组合值的随机模式。 |
| 复位值 | `parameter bit` | 汇总保留 field 的复位值，并按归一化位段排列。 |
| field 约束 | `constraint` | 将每个 field 与组合值中的归一化位段建立等式。 |

所有变量加入 UVM field 自动化。组合值和 field 使用十六进制打印，随机锁使用 `UVM_NOPRINT`。`pre_randomize` 先调用父类实现，再处理随机锁。

例如保留 field 位于原始寄存器的 bit 4 与 bit 8 到 bit 10，有效范围为 bit 4 到 bit 10。组合值宽度为 7，原始 bit 4 映射到组合值 bit 0，原始 bit 8 到 bit 10 映射到组合值 bit 4 到 bit 6。中间未定义位保留在组合值中，但不增加 field 约束。

## block 与 system 类

block 与 system 类继承统一配置的 `base_class`，并将直接子 reg、block 或 system 声明为 `rand` 对象成员。构造函数通过 UVM factory 创建成员。固定数量的实例数组使用静态数组和对应的 UVM field 宏。

依赖排序只保证被引用类型先于引用类型。RALF 层次不需要额外拼接，类成员实例会自然恢复相同关系。一个输出文件包含多个 class，这是依赖顺序与单文件交付要求共同形成的例外。

## 寄存器模型同步

`emit_ral_sync_methods` 启用后，每个类增加一组同步方法。

- reg 的 set 方法调用寄存器对象的 `set`，将组合值写入寄存器模型镜像。
- reg 的 get 方法分别读取 field 和寄存器值，再置位随机锁。
- block 与 system 将对应成员传给下一级配置对象，递归执行相同方法。

这些方法只同步寄存器模型中的值，不执行 DUT 前门或后门访问。

## RALF 加载

`models.py` 解析 `ralf_file` 与 `include_dirs` 后，调用内部 `ralf_model.load_ralf_file`。加载器负责读取文本、递归展开 `source`、解析 RALF 语法并返回包含 system、block、reg 与 field 的对象树。cfggen 的语义整理层随后解析实例引用、过滤访问方式并建立输出模型。

`ralf_model` 是 cfggen 自带的普通 Python 子模块，不是外部导入包，也不是独立可执行文件。它只负责 RALF 文本、语法对象和源文件展开。运行时使用的 Pydantic 已包含在 Jinja 构建环境中，因此不增加额外安装步骤。

`ralfconv` 是建立在 RALF 解析结果之上的独立命令行转换器，适合输出扁平或层次 JSON，用于交换和检查寄存器描述。cfggen 不经过该 JSON 中间层，以便直接保留定义、实例与源文件结构，并减少一个可执行程序和一次格式转换。

## 校验边界

- field 访问方式按小写匹配忽略列表。
- reset 不接受包含未知态的字面量。
- 实例数组只接受固定正整数数量。
- 未解析引用、循环依赖、重名、重叠位段与固定成员冲突会中止生成。
- reg 中全部 field 被忽略后，该 reg 不出现在所属 block 中。

# 输入配置

渲染前，工具先把配置文件读成 dict，再交给 `models.py` 里的入口类。下列能力由 **configlib** 提供；扩展名常见 `.yaml`、`.yml`、`.json`、`.json5`、`.toml`、`.csv` 等，由加载器按后缀选择。

## 变量 `${…}`

解析在配置文件内完成，展开后的 dict 才进入 `models.py`。模板里写的是**已经解析好的字段**，不要在 `.j2` 里再写 `${}`。

| 写法 | 含义 |
| --- | --- |
| `${vars.prefix}` | 从根上的 `vars.prefix` 取值 |
| `${paths.base}` | 点分路径，引用已存在的键 |
| `${project_name}-build` | 字符串内嵌引用 |
| `${..key}` | 相对当前 mapping 向上一层再取 `key` |
| `${env:NAME}` | 读环境变量 |
| `${env:NAME:默认值}` | 环境变量缺失时用默认值 |

部分格式里，单独占一行的 `${…}` 会参与列表展开或 mapping 深合并，具体以所用格式与加载器为准。

标量会自动尝试转成 `int`、`float`、`bool` 或 `null`；转不了则保留字符串。

## `!include`

在支持该标签的格式里，路径相对**当前文件所在目录**。

```yaml
defaults: !include defaults.yaml
parts:
  !include part_a.yaml
  !include part_b.yaml
```

同一 mapping 下多行 `!include` 会**深合并**字典；后出现的键覆盖先前的同名键。循环引用会报错。不支持 `!include` 的格式须拆成多个文件，由载入方式决定如何合并。

## 单文件捆绑 `#文件名`

部分载入工具支持：首条非空行形如 `#a.yaml`，把一个物理文件拆成多段虚拟文件；**第一段**为入口，段内仍可用 `!include` 引用同捆绑里的其它段名。

```yaml
#a.yaml
!include spec.yaml
name: main
items: ${vars.items}

# spec.yaml
vars:
  items:
    !include items.json
```

是否支持此种写法取决于实际使用的载入命令，与 configlib 的 `${}`、`!include` 可组合使用。

## 示例：变量与引用

```yaml
vars:
  prefix: acme
  version: 3
paths:
  base: ${vars.prefix}_root
project_name: ${vars.prefix}-app-v${vars.version}
output_dir: ${paths.base}/out
nested:
  label: ${project_name}-build
```

## 与模板的关系

```text
配置文件 --> dict --> Models(**dict) --> 实例 --> 模板中的 {{ 字段 }}
```

各单元 `README.md` 只描述**该单元**有哪些键、类型与默认值；本页只说明**怎么写配置文件本身**。

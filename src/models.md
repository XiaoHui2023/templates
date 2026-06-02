# models.py

每个模板单元目录里的 `models.py` 描述输入配置的字段与类型，并供模板使用。加载时会把该目录加入模块搜索路径，再导入此文件。

## 入口类放在最后

文件中**最后一个** `class` 是入口类，一般命名为 `Models`。配置 dict 用 `Models(**data)` 实例化。

此文件里**更靠前的** `class` 会注册为模板**全局类型名**，例如 `Settings`、`Tree`，在 `.j2` 里可按类型名引用，不必实例化。

```python
from pydantic import BaseModel, Field
from nodes import Tree

class Settings(BaseModel):
    class_prefix: str = Field("prefix_", min_length=1)

class Models(BaseModel):
    settings: Settings
    items: list[Tree]
```

`Tree` 等复杂类型可放在同目录的 `nodes.py`，由 `models.py` 绝对导入。

## 导入方式

跨文件用**同目录模块名**绝对导入：

```python
from nodes import Tree, ItemBase
```

不要用 `from .nodes import …`。不要把上层仓库路径写进 import。

## 类怎么写

| 方式 | 适用 |
| --- | --- |
| 普通 `class` | 简单容器、少量逻辑 |
| `@dataclass` | 字段为主、无复杂校验 |
| **Pydantic `BaseModel`** | **推荐**：类型、默认值、`Field` 说明、校验器 |

根 `Models` 常用 `extra="ignore"` 以保留配置里多写的顶层键；嵌套模型用 `extra="forbid"` 以便笔误键报错。

## 函数与 property

- **模块级函数**：解析、共用计算，供多个类或校验器调用。
- **实例方法**：若以非 `_` 开头，主入口类上的方法还可注册为模板**过滤器**，管道写法 `{{ '' | method_name }}`。
- **`@property` / `computed_field`**：由代码算出的只读字段会进入模板上下文，与配置文件里填写的字段一样用 `{{ name }}` 读取。

```python
class Models(BaseModel):
    items: list[Tree]

    @computed_field
    @property
    def item_count(self) -> int:
        return len(self.items)
```

## 模板里看到什么

入口类实例化后，字段与 property 成为模板的**根部变量**；嵌套对象按属性继续访问。

```jinja
{{ settings.class_prefix }}
{% for item in items %}
  {{ item.name }}
{% endfor %}
```

`models.py` 里在 `Models` 之前定义的类名，例如 `Settings`，在全局作用域可用类型名 `Settings`，供模板按类型区分生成内容。

数据流：

```text
配置文件 --> Models 实例 --> 整理为 dict --> {{ 字段名 }}、…
```

各单元的字段表写在对应目录 `README.md`，不在此重复。

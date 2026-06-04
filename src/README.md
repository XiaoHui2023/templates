# 目录

自顶向下可有多级路径；含 `models.py` 的目录即一个可单独配置的模板单元。单元根即该目录，常见文件如下。

```text
<路径段>/<路径段>/…/<模板单元>/
  models.py          # 字段与类型；末尾 class 一般为 Models
  example.yaml       # 示例输入
  README.md          # 该单元配置字段
  nodes.py           # 可选，从 models.py 拆出的同目录代码
  all.f.j2           # 部分单元带编译清单
  <子目录>/          # 单元内可有更多源文件与子目录
```

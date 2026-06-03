# 模板仓库

`src/` 根上的 `input.md`、`models.md` 说明配置文件写法与 `models.py` 约定。子目录内为可独立渲染的模板单元；单元根目录常见布局如下。

```text
<模板单元>/
  models.py          # 输入配置的字段与类型；入口类在末尾，一般为 Models
  example.yaml       # 示例输入
  README.md          # 该单元配置字段
  *.j2               # 模板；相对路径保留，去掉 .j2 即为输出文件名
  nodes.py           # 可选，从 models.py 拆出的同目录代码
  all.f.j2           # 部分单元另有编译清单
  <子目录>/
    *.j2             # 也可全部 *.j2 与 models.py 同级
```

# pll_mini 测试

本目录专门验证 pll_mini 的 RALF 读取与 consolver 约束求解，与 **`src/c/pll_mini`** 交付内容分离。

## 目录

```text
test/c/pll_mini/
  bin/windows/          # consolver.exe、ralf-conv.exe
  fixtures/             # 测试 YAML 与 example.ralf 副本
  test_resolve.py       # 单元测试
  run_tests.bat         # 一键运行
```

## 运行

```bat
run_tests.bat
```

Linux 或 Git Bash 下：

```bash
python test_resolve.py -v
```

测试会自动把 **`PYTHONPATH`** 设为 **`src/c/pll_mini`**。Windows 上优先使用 **`test/c/pll_mini/bin/windows/`** 下的可执行体；Ubuntu 上使用 **`src/c/pll_mini/bin/linux/`**，无需额外设置权限。

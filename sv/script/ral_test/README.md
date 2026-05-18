# ral_test

适用于已建立 RAL 并打通总线访问的环境，按配置依次启动多个 UVM 内建寄存器测试 sequence。

启用 **`access`** 时，除 **`seq.sv`** 外还会生成 **`reg_fd_single_seq.sv`** 与 **`reg_fd_access_seq.sv`**。交付物**默认不使用** `` `include`` 拼接；**filelist** 须按依赖顺序列出 **`reg_fd_single_seq.sv`**、**`reg_fd_access_seq.sv`**、**`seq.sv`**（或你重命名后的等价文件名），**勿**只编 **`seq.sv`** 而漏掉前两者。

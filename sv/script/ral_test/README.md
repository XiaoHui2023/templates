# ral_test

适用于已建立 RAL 并打通总线访问的环境，按配置依次启动多个 UVM 内建寄存器测试 sequence。

启用 **`access`** 时，除 **`seq.sv`** 外还会生成 **`reg_fd_single_seq.sv`** 与 **`reg_fd_access_seq.sv`**；二者由 **`seq.sv`** 内 `` `include`` 拉入。**filelist 只须列 `seq.sv`**（或你重命名后的入口文件），**不要**再把上述两个辅助文件单独加入编译列表，以免重复定义。

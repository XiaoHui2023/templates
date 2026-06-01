# ral_test

适用于已建立 RAL 并打通总线访问的环境，按配置依次启动寄存器自测 sequence；`reset` 与 `access` 为仅前门的自实现检查，其余开关仍使用 UVM 内建 sequence。

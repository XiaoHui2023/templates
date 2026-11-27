# DW eMMC Compile Gate

Use Python with `pyslang==12.1.0` and the [Accellera UVM 1.2 reference implementation](https://www.accellera.org/downloads/standards/uvm). Set `DW_EMMC_UVM_SRC` to the extracted `src` directory. If pyslang is installed in a separate directory, set `DW_EMMC_PYSLANG_PATH` to it. The ignored `.codex/toolchain.local.json` accepts `dw_emmc_uvm_src` and `dw_emmc_pyslang_path` instead.

```text
python tools/check_dw_emmc_generation.py
python tools/check_dw_emmc_compile.py <generated-directory> mshc
```

The generation gate elaborates an integration top for each generated `all.f`, in listed order, without enabling forward-use compatibility. It uses actual Accellera UVM and a frozen test-only RAL declaration contract. This does not validate proprietary SVT or RAL names, addresses, field widths or DUT behavior. The negative control moves the sequencer after the base request and requires the compiler to reject that dependency by name.

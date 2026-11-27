"""Elaborate the complete generated filelist with UVM 1.2 and a test-only RAL."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory


TOOLS = Path(__file__).resolve().parent


def toolchain():
    local = TOOLS.parent / ".codex/toolchain.local.json"
    config = json.loads(local.read_text(encoding="utf-8")) if local.is_file() else {}
    slang_path = os.environ.get("DW_EMMC_PYSLANG_PATH") or config.get("dw_emmc_pyslang_path")
    if slang_path:
        sys.path.insert(0, str(Path(slang_path).resolve()))
    try:
        import pyslang
    except ImportError as error:
        raise RuntimeError("Install pyslang==12.1.0 for the DW eMMC compile gate") from error
    if pyslang.__version__ != "12.1.0":
        raise RuntimeError(f"DW eMMC compile gate requires pyslang 12.1.0, got {pyslang.__version__}")
    uvm_src = os.environ.get("DW_EMMC_UVM_SRC") or config.get("dw_emmc_uvm_src")
    uvm = Path(uvm_src).resolve() if uvm_src else None
    if uvm is None or not (uvm / "uvm_pkg.sv").is_file() or not (uvm / "uvm_macros.svh").is_file():
        raise RuntimeError("Set DW_EMMC_UVM_SRC to the Accellera UVM 1.2 src directory")
    if not re.search(r"\bbit\s+big_endian\b", (uvm / "base/uvm_packer.svh").read_text(encoding="utf-8")):
        raise RuntimeError("The generated ADMA packer uses the Accellera UVM 1.2 endian API")
    return uvm


def fixture_ral(controller):
    """Build the mock from a frozen contract, never from the candidate's references."""
    chip = {"mshc": "DWC_mshc", "mobile_storage": "DWC_mobile_storage"}[controller]
    roles = {"rm": {}, "rm_vd1": {}}
    current = ""
    for line in (TOOLS / "dw_emmc_compile_ral.txt").read_text(encoding="ascii").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 1:
            current = parts[0]
        elif current == controller:
            role, reg, *fields = parts
            roles[role][reg] = fields
    if not roles["rm"]:
        raise ValueError(f"empty compile fixture for {controller}")

    yield "package svt_uvm_pkg; endpackage"
    regmodel_members = []
    for role, suffix in (("rm", "block"), ("rm_vd1", "vendor1_block")):
        member = f"{chip}_map_{chip}_{suffix}"
        block = f"ral_block_{member}"
        for reg, fields in roles[role].items():
            yield f"virtual class fixture_{role}_{reg} extends uvm_pkg::uvm_reg;"
            yield 'function new(); super.new("fixture", 32, uvm_pkg::UVM_NO_COVERAGE); endfunction'
            yield from (f"uvm_pkg::uvm_reg_field {field};" for field in fields)
            yield "endclass"
        yield f"virtual class {block} extends uvm_pkg::uvm_reg_block;"
        yield from (f"fixture_{role}_{reg} {reg};" for reg in roles[role])
        yield "endclass"
        regmodel_members.append(f"{block} {member};")
    yield f"virtual class ral_sys_{chip} extends uvm_pkg::uvm_reg_block;"
    yield from regmodel_members
    yield "endclass"


def compile_filelist(output, uvm, controller, *, bad_order=False):
    from pyslang import DiagnosticEngine
    from pyslang.driver import Driver

    with TemporaryDirectory(prefix="dw-emmc-compile-") as directory:
        work = Path(directory)
        ral = work / "fixture_ral.sv"
        ral.write_text("\n".join(fixture_ral(controller)) + "\n", encoding="ascii")
        agent_source = (output / "component/agent.sv").read_text(encoding="utf-8")
        prefix = re.search(r"^class (\w+_)agent extends", agent_source, re.M)[1]
        top = work / "fixture_top.sv"
        top.write_text(f"""module fixture_top;
    {prefix}agent agent;
    {prefix}interface vif();
    initial begin
        agent = new();
        agent.settings.vif = vif;
        agent.sqr.rw_test();
    end
endmodule
""", encoding="ascii")
        filelist = output / "all.f"
        if bad_order:
            listed = filelist.read_text(encoding="utf-8").splitlines()
            listed.remove("component/sequencer.sv")
            listed.insert(listed.index("sequence/base.sv"), "component/sequencer.sv")
            filelist = work / "wrong-order.f"
            filelist.write_text("\n".join(f'"{(output / path).as_posix()}"' for path in listed if path),
                                encoding="utf-8")

        cmd = ["slang", "--single-unit", "--top", "fixture_top", "--timescale", "1ns/1ps",
               "-DUVM_NO_DPI", f'-I"{uvm.as_posix()}"', f'"{(uvm / "uvm_pkg.sv").as_posix()}"',
               f'"{ral.as_posix()}"', "-F", f'"{filelist.as_posix()}"', f'"{top.as_posix()}"']
        driver = Driver()
        driver.addStandardArgs()
        if not driver.parseCommandLine(" ".join(cmd)) or not driver.processOptions() or not driver.parseAllSources():
            raise RuntimeError(f"unable to parse complete filelist {filelist}")
        compilation = driver.createCompilation()
        errors = [diag for diag in compilation.getAllDiagnostics() if diag.isError()]
        if bad_order:
            diagnosis = DiagnosticEngine.reportAll(compilation.sourceManager, errors)
            expected = f"'{prefix}sequencer' used before its declaration"
            if expected not in diagnosis or "req.sv" not in diagnosis:
                raise RuntimeError("strict compiler did not detect the reintroduced sequencer ordering bug")
        elif errors:
            first = DiagnosticEngine.reportAll(compilation.sourceManager, errors[:15])
            raise RuntimeError(f"{filelist} failed strict semantic compilation ({len(errors)} errors):\n{first}")
        if [item.name for item in compilation.getRoot().topInstances] != ["fixture_top"]:
            raise RuntimeError("strict compiler did not elaborate the integration fixture")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path)
    parser.add_argument("controller", choices=["mshc", "mobile_storage"])
    args = parser.parse_args()
    compile_filelist(args.generated.resolve(), toolchain(), args.controller)

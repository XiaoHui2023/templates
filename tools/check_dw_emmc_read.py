"""Render dw_emmc configurations and check the generated PIO read contract."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "src/sv/agent/dw_emmc"
COMMAND = Path("sequence/operation/command/op.sv")
RW_TEST = Path("sequence/test/rw.sv")
TOOLS = Path(__file__).resolve().parent


def method(source, name, owner="command_operation_seq"):
    match = re.search(rf"^task \w+{owner}::{name}\([^\n]*\);\n(.*?)^endtask",
                      source, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"missing command method: {name}")
    return re.sub(r"//[^\n]*|\s+", "", match[1])


def ordered(body, *events):
    for event in events:
        offset = body.find(event)
        if offset < 0:
            raise ValueError(f"missing or misordered event: {event}")
        body = body[offset + len(event):]


def verify(source, *, mobile, dma):
    for hook in ("read", "read_buffer", "read_buffer_blocked",
                 "read_buffer_one_block", "wait_xfer_complete"):
        if not re.search(rf"^\s*extern\s+virtual\s+(?:protected\s+)?task\s+{hook}\(", source, re.M):
            raise ValueError(f"nonvirtual extension hook: {hook}")
    read = method(source, "read")
    ordered(read, "if(cmd_request.rd_blocking)beginread_buffer_blocked(data);",
            "elsebeginread_buffer(data);wait_xfer_complete();")
    if dma:
        ordered(read, "if(cmd_request.dma_enable)begin", "wait_xfer_complete();", "read_memory(data);", "elsebegin")
    elif "read_memory(" in read:
        raise ValueError("DMA read in a PIO-only build")
    drain = method(source, "read_buffer")
    ordered(drain, "for(intj=0;j<cmd_request.block_count;j++)begin",
            "wait_read_buffer_ready();", "read_buffer_one_block(data);")
    ready = method(source, "wait_read_buffer_ready")
    if mobile:
        ordered(ready, "if(cmd_request.rd_blocking)return;", "buf_rd_ready==1;")
    elif "return;" in ready or "buf_rd_ready==1;" not in ready:
        raise ValueError("BRR is not mandatory for MSHC PIO")
    blocked = method(source, "read_buffer_blocked")
    if "read_buffer_one_block(" in blocked:
        raise ValueError("blocked read bypasses the shared drain")
    if mobile:
        ordered(blocked, "wait_xfer_complete();", "read_buffer(data);")
        ordered(method(source, "read_buffer_one_block"), "wait_read_fifo_not_empty(", "p_sequencer.cpu_read(")
    else:
        ordered(blocked, "read_buffer(buffered);", "wait_xfer_complete();", "data={data,buffered};")
        if blocked.count("wait_xfer_complete();") != 1:
            raise ValueError("expected exactly one completion wait")


def calibrate(source):
    mutations = (
        ("extern virtual task read(", "extern task read("),
        ("if (cmd_request.rd_blocking)", "if (!cmd_request.rd_blocking)"),
        ("wait_read_buffer_ready();\n        read_buffer_one_block", "read_buffer_one_block"),
        ("read_buffer(buffered);", "read_buffer_one_block(buffered);"),
        ("wait_xfer_complete();\n    data = {data, buffered};",
         "data = {data, buffered};\n    wait_xfer_complete();"),
    )
    for before, after in mutations:
        if before not in source:
            raise ValueError(f"cannot calibrate oracle: {before}")
        try:
            verify(source.replace(before, after, 1), mobile=False, dma=False)
        except ValueError:
            continue
        raise ValueError(f"oracle accepted fault: {after}")


def check_rw_test(source):
    text = re.sub(r"//[^\n]*|\s+", "", source)
    if "if(rd){rd_single||rd_multi;}" not in text:
        raise ValueError("rd_blocking cannot substitute for enabling a read")
    for mode in ("rd_single", "rd_multi"):
        match = re.search(rf"if\({mode}\)begin`uvm_do_with\(read_seq,(.*?)\}}\)", text)
        if not match or "blocking==local::rd_blocking;" not in match[1]:
            raise ValueError(f"{mode} does not propagate read mode")


def simulate(output, *flags):
    if shutil.which("verilator"):
        args = [sys.executable, str(TOOLS / "run_dw_emmc_read_probe.py")]
        generated = output
    elif os.name == "nt":
        docker = Path.home() / ".cursor/skills/docker-agent-environment/scripts/docker-safe-run.ps1"
        args = ["pwsh", "-NoProfile", "-File", str(docker), "run", "--rm", "--pull", "never",
                "--network", "none", "--mount", f"type=bind,source={output},target=/generated,readonly",
                "--mount", f"type=bind,source={TOOLS},target=/probe,readonly", "codex-sv-uvm:5.052",
                "python3", "/probe/run_dw_emmc_read_probe.py"]
        generated = "/generated"
    else:
        raise RuntimeError("Verilator is required for the generated read operation probe")
    target = generated if {"--hot-paths", "--inline-phase"}.intersection(flags) else f"{generated}/{COMMAND.as_posix()}"
    subprocess.run([*args, str(target), *flags], check=True, timeout=40)


def jinja_builder():
    configured = os.environ.get("JINJA_BUILD_EXECUTABLE")
    local = ROOT / ".codex/toolchain.local.json"
    if configured is None and local.is_file():
        configured = json.loads(local.read_text(encoding="utf-8")).get("jinja_build")
    executable = shutil.which(configured or "jinja-build")
    if not executable:
        raise RuntimeError("Set JINJA_BUILD_EXECUTABLE or .codex/toolchain.local.json's jinja_build "
                           "to the project renderer executable")
    return executable


def main():
    builder = jinja_builder()
    variants = (("mshc", "emmc", False), ("mshc", "sdcard", False),
                ("mshc", "sdio", True), ("mobile_storage", "sdio", True))
    with tempfile.TemporaryDirectory(prefix="dw-emmc-read-") as temp:
        for controller, card, dma in variants:
            name = f"{controller}-{card}"
            output = Path(temp) / name
            config = FAMILY / "example.yaml"
            if card != "emmc":
                config = output.with_suffix(".yaml")
                config.write_text(f"controller_ip: {controller}\ncard_type: {card}\nenable_dma: {str(dma).lower()}\n",
                                  encoding="ascii")
            result = subprocess.run([builder, str(FAMILY), str(config), str(output)],
                                    capture_output=True, timeout=20)
            if result.returncode:
                raise RuntimeError(f"{name} render failed: {(result.stdout + result.stderr).decode(errors='replace')}")
            source = (output / COMMAND).read_text(encoding="utf-8")
            verify(source, mobile=controller == "mobile_storage", dma=dma)
            check_rw_test((output / RW_TEST).read_text(encoding="utf-8"))
            if card == "emmc":
                calibrate(source)
            print(f"PASS {name}: generated read structure and ordering", flush=True)
        for controller, card, dma in variants:
            flags = (["--mobile"] if controller == "mobile_storage" else []) + (["--dma"] if dma else [])
            simulate(Path(temp) / f"{controller}-{card}", *flags)
        simulate(Path(temp) / "mshc-emmc", "--hot-paths")
        simulate(Path(temp) / "mshc-emmc", "--inline-phase")


if __name__ == "__main__":
    main()

"""Execute the generated read methods with recording FIFO and interrupt substitutes."""

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_probe(work, top, flags, timeout=40, jobs=2):
    command = ["verilator", "--binary", "--timing", "-Wno-fatal", "-j", str(jobs),
               "--top-module", top, "--Mdir", str(work), *flags, str(ROOT / f"{top}.sv")]
    build = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if build.returncode:
        raise RuntimeError(build.stdout + build.stderr)
    return str(work / f"V{top}")


def run_probe(generated, expected_baseline, uvm_src=None, mobile=False, dma=False):
    source = generated.read_text(encoding="utf-8")
    class_name = re.search(r"^class (\w+command_operation_seq)\s*#\(", source, re.M)
    if not class_name:
        raise ValueError("missing parameterized command operation")
    names = {"read", "read_buffer", "read_buffer_blocked", "read_buffer_one_block",
             "wait_xfer_complete", "wait_read_buffer_ready"}
    declarations = re.findall(r"^\s*(extern (?:\w+ )*task (\w+)\([^\n]*\);)$", source, re.M)
    definitions = re.findall(r"^(task \w+command_operation_seq::(\w+)\(.*?^endtask)$",
                             source, re.M | re.S)
    mocked = {"read_buffer_one_block", "wait_xfer_complete"}
    if dma:
        names.add("read_memory")
        mocked.add("read_memory")
    required = names - ({"wait_read_buffer_ready"} if expected_baseline else set())
    if {name for _, name in declarations if name in names} != required:
        raise ValueError("generated declarations do not match the probe")
    if {name for _, name in definitions if name in names} != required:
        raise ValueError("generated definitions do not match the probe")

    with tempfile.TemporaryDirectory(prefix="dw-emmc-read-probe-") as temp:
        work = Path(temp)
        (work / "declarations.svh").write_text(
            "\n".join(text for text, name in declarations if name in names), encoding="utf-8")
        (work / "methods.svh").write_text(
            "\n".join(text for text, name in definitions if name in names - mocked), encoding="utf-8")
        flags = [f"-I{work}", f"-DPROBE_COMMAND_TYPE={class_name[1]}"]
        if mobile:
            flags.append("-DDW_EMMC_MOBILE_PROBE")
        if dma:
            flags.append("-DDW_EMMC_DMA_PROBE")
        if uvm_src:
            flags += ["-MAKEFLAGS", "OPT_FAST=-O0 OPT_SLOW=-O0", "-DUVM_NO_DPI",
                      "-DDW_EMMC_FACTORY_PROBE", f"-I{uvm_src}", str(uvm_src / "uvm_pkg.sv")]
        binary = build_probe(work, "dw_emmc_read_probe", flags, 180 if uvm_src else 40)
        for blocks in (1, 3):
            cases = (
                (["+dispatch"], "derived method was not dispatched"),
                (["+blocking"], "TC before all blocks were drained"),
            )
            if not expected_baseline:
                cases += ((["+dispatch", "+blocking"], None),)
                if dma:
                    cases += ((["+dma", "+dispatch"], None), (["+dma", "+blocking"], None))
            for flags, baseline_error in cases:
                result = subprocess.run([binary, f"+blocks={blocks}", *flags],
                                        capture_output=True, text=True, timeout=5,
                                        cwd=work)
                trace = result.stdout + result.stderr
                if uvm_src and "FACTORY_PROBE_CREATED" not in trace:
                    raise RuntimeError(f"probe did not prove the factory result: {trace}")
                if expected_baseline:
                    if result.returncode == 0 or baseline_error not in trace:
                        raise RuntimeError(f"baseline did not reproduce {baseline_error}: {trace}")
                elif result.returncode or "READ_PROBE_PASS" not in trace:
                    raise RuntimeError(f"read probe failed: {trace}")
                print(f"{'BASELINE REJECTED' if expected_baseline else 'PASS'} {blocks=} {flags}", flush=True)


def run_clock_phase_probe(generated):
    with tempfile.TemporaryDirectory(prefix="dw-emmc-phase-probe-") as temp:
        work = Path(temp)
        binary = build_probe(work, "dw_emmc_clock_phase_probe",
                             [f"-I{generated}", "--no-sched-zero-delay"])
        for case in ("no_adapter", "empty_topology", "success", "bad_axis", "budget", "busy",
                     "apply_failed", "no_window", "restore_fail", "restore_timeout",
                     "confirmation_fail", "timeout", "first_probe_timeout"):
            result = subprocess.run([binary, f"+test={case}"], cwd=work, capture_output=True,
                                    text=True, timeout=5)
            if result.returncode or f"PHASE_PROBE_PASS {case}" not in result.stdout:
                raise RuntimeError(f"phase probe failed: {result.stdout}{result.stderr}")
            print(f"PASS clock phase {case}", flush=True)


def run_automatic_phase_probe(generated, uvm_src):
    with tempfile.TemporaryDirectory(prefix="dw-emmc-auto-phase-") as temp:
        work = Path(temp)
        flags = [f"-I{generated}", f"-I{uvm_src}", "-DUVM_NO_DPI",
                 "-MAKEFLAGS", "OPT_FAST=-O0 OPT_SLOW=-O0", str(uvm_src / "uvm_pkg.sv")]
        jobs = max(1, min(6, len(os.sched_getaffinity(0)))) if hasattr(os, "sched_getaffinity") else 2
        binary = build_probe(work, "dw_emmc_auto_phase_probe", flags, 70, jobs)
        result = subprocess.run([binary, "+UVM_NO_RELNOTES"], cwd=work, capture_output=True, text=True, timeout=5)
        if result.returncode or "AUTO_PHASE_PROBE_PASS" not in result.stdout or "[RNDFLD]" in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        failed = subprocess.run([binary, "+UVM_NO_RELNOTES", "+reject_transfer"], cwd=work,
                                capture_output=True, text=True, timeout=5)
        if (not re.search(r"UVM_FATAL .*\[CLOCK_PHASE\].*status=PHASE_NO_WINDOW", failed.stdout)
                or "AUTO_PHASE_PROBE_PASS" in failed.stdout
                or "no-window phase returned into the normal flow" in failed.stdout
                or "[RNDFLD]" in failed.stdout):
            raise RuntimeError(failed.stdout + failed.stderr)
        print("PASS automatic phase ordering, bypass, cache, reset, overlap and no-window rejection")


def run_hot_path_probe(generated, expected_baseline):
    command = (generated / "sequence/operation/command/op.sv").read_text(encoding="utf-8")
    fifo_read = re.search(r"^task \w+command_operation_seq::read_buffer_one_block\(.*?^endtask$",
                          command, re.M | re.S)
    with tempfile.TemporaryDirectory(prefix="dw-emmc-hot-path-") as temp:
        work = Path(temp)
        (work / "fifo_read.svh").write_text(fifo_read[0], encoding="utf-8")
        binary = build_probe(work, "dw_emmc_hot_path_probe", [f"-I{generated}", f"-I{work}"])
        result = subprocess.run([binary, "+dense_only"], capture_output=True, text=True, timeout=5)
        if result.returncode or "HOT_PATH_PROBE_PASS" not in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        # Bound the old dense allocator instead of letting a high-address repro exhaust the host.
        command = ["sh", "-c", 'ulimit -c 0; ulimit -v 400000; exec "$1"', "sh", binary]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            if not expected_baseline:
                raise
            print("BASELINE REJECTED: 4 GiB write exceeded its time budget")
            return
        if expected_baseline:
            if not result.returncode or "bad_alloc" not in result.stderr:
                raise RuntimeError(result.stdout + result.stderr)
            print("BASELINE REJECTED: 4 GiB write exceeded its memory budget")
        elif result.returncode or "HOT_PATH_PROBE_PASS" not in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        else:
            print("PASS sparse boot address and linear FIFO byte append")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("generated", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--uvm-src", type=Path)
    parser.add_argument("--mobile", action="store_true")
    parser.add_argument("--dma", action="store_true")
    probes = parser.add_mutually_exclusive_group()
    probes.add_argument("--clock-phase", action="store_true")
    probes.add_argument("--automatic-phase", action="store_true")
    probes.add_argument("--hot-paths", action="store_true")
    arguments = parser.parse_args()
    if arguments.clock_phase:
        run_clock_phase_probe(arguments.generated)
    elif arguments.automatic_phase:
        if arguments.uvm_src is None:
            parser.error("--automatic-phase requires --uvm-src")
        run_automatic_phase_probe(arguments.generated, arguments.uvm_src)
    elif arguments.hot_paths:
        run_hot_path_probe(arguments.generated, arguments.baseline)
    else:
        run_probe(arguments.generated, arguments.baseline, arguments.uvm_src, arguments.mobile, arguments.dma)

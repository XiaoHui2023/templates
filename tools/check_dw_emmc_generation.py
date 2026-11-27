"""Check conditional DW eMMC products against their compile lists."""

from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tempfile

from check_dw_emmc_read import FAMILY
from check_dw_emmc_compile import compile_filelist, toolchain
from check_sv_declaration_ownership import check_source, self_test
from check_sv_filelist_order import check_type_order, self_test as order_self_test
from check_template_pruning import ROOT, renderer


CONTROLLERS = (("mshc", "emmc"), ("mshc", "sdcard"), ("mshc", "sdio"), ("mobile_storage", "sdio"))
DESCRIPTORS = {"mshc": "model/data/adma_des.sv", "mobile_storage": "model/data/idmac_descriptor.sv"}
DMA_TEST = "sequence/test/dma.sv"
CLOCK = "contract_clock"


def verify(files, controller, card, dma, clock):
    listed = [name for name in files["all.f"].splitlines() if name]
    sources = {path for path in files if path.endswith(".sv")}
    if len(listed) != len(sources) or set(listed) != sources:
        raise ValueError(f"incorrect all.f: missing={sorted(sources - set(listed))}, "
                         f"unbuilt={sorted(set(listed) - sources)}, repeated={len(listed) - len(set(listed))}")
    for path in sources:
        check_source(files[path], path)
    check_type_order(files, listed)
    if any("clock_phase" in path or re.search(r"\b(?:calibrate_clock_phases|clock_phase_\w+)\b", files[path])
           for path in sources):
        raise ValueError("withdrawn clock phase adapter or calibrator is still generated")

    dma_sources = {*DESCRIPTORS.values(), DMA_TEST}
    expected = {DESCRIPTORS[controller], DMA_TEST} if dma else set()
    if sources & dma_sources != expected:
        raise ValueError("Incorrect DMA file set")
    kit = files["component/kit_sequencer.sv"]
    for symbol in ("dma_test", "use_dma"):
        if bool(re.search(rf"\b{symbol}\b", kit)) != dma:
            raise ValueError(f"DMA API presence disagrees with enable_dma: {symbol}")
    for path in ("top/interface.sv", "top/monitor_interface.sv"):
        if bool(re.search(rf"\b{CLOCK}\b", files[path])) != clock:
            raise ValueError(f"monitor clock presence disagrees with enable: {path}")
        for pin in ("link_chip_clk", "link_card_clk"):
            if bool(re.search(rf"\binput wire {pin}\b", files[path])) != (card == "emmc"):
                raise ValueError(f"phase clock port disagrees with card type: {path}:{pin}")

    phase_argument = re.search(r"extern task rw_test\([^\n]*, bit auto_clock_phase = 0\);", kit)
    phase_route = "auto_clock_phase == local::auto_clock_phase;"
    if (bool(phase_argument) != (card == "emmc")
        or kit.count(phase_route) != int(card == "emmc")):
        raise ValueError("incorrect rw_test phase switch default or route")
    phase_flow = files["sequence/test/rw.sv"]
    phase_before_io = re.search(
        r"if \(auto_clock_phase\)\s*apply_measured_link_phase\(\);\s*if\(wr_single\)", phase_flow)
    if bool(phase_before_io) != (card == "emmc"):
        raise ValueError("link measurement must run once before the existing I/O branches")
    if phase_flow.count("cb.apply_link_phase(") != int(card == "emmc"):
        raise ValueError("link phase must be passed through exactly one callback")
    if card == "emmc" and (
        not re.search(r"one_way_deg = 360\.0 \* real'\(propagation_fs\) / real'\(period_fs\);\s*"
                      r"cb\.apply_link_phase\([^;]*one_way_deg, 2\.0 \* one_way_deg, applied\);", phase_flow)
        or re.search(r"\bforce\b", files["top/monitor_interface.sv"])
    ):
        raise ValueError("link phase must use the measured period and only estimate the round trip")
    if card != "emmc" and any(re.search(r"\b(?:auto_clock_phase|apply_link_phase|measure_link_clock)\b",
                                       files[path]) for path in sources):
        raise ValueError("phase code leaked outside eMMC")


def main():
    reports = {}
    rejected = 0
    self_test()
    order_self_test()
    executable = renderer()
    uvm = toolchain()
    with tempfile.TemporaryDirectory(prefix="dw-emmc-generation-") as temporary:
        work = Path(temporary)
        for (controller, card), dma, clock in product(CONTROLLERS, (False, True), (False, True)):
            config = work / "input.yaml"
            name = f"{controller}-{card}-dma{int(dma)}-monitor{int(clock)}"
            output = work / name
            config.write_text(json.dumps({"controller_ip": controller, "card_type": card, "enable_dma": dma,
                                         "monitored_clocks": [{"name": CLOCK, "enable": clock}]}), encoding="utf-8")
            result = subprocess.run([executable, str(FAMILY), str(config), str(output)],
                                    capture_output=True, timeout=25)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            files = {p.relative_to(output).as_posix(): p.read_text(encoding="utf-8")
                     for p in output.rglob("*") if p.is_file()}
            try:
                verify(files, controller, card, dma, clock)
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from error
            compile_filelist(output, uvm, controller)
            if (controller, card, dma, clock) == ("mshc", "emmc", False, False):
                compile_filelist(output, uvm, controller, bad_order=True)
                rejected += 1
            reports[name] = len(files)
            if not dma and not clock:
                bad_order = files["all.f"].splitlines()
                bad_order.remove("component/sequencer.sv")
                bad_order.insert(bad_order.index("sequence/base.sv"), "component/sequencer.sv")
                try:
                    verify(files | {"all.f": "\n".join(bad_order)}, controller, card, dma, clock)
                except ValueError as error:
                    if "sequence/operation/base/req.sv" not in str(error) or "used before" not in str(error):
                        raise
                    rejected += 1
                else:
                    raise ValueError("generated filelist accepted request before sequencer")
                controls = [("component/kit_sequencer.sv", "extern task dma_test();"),
                            ("top/interface.sv", f"input wire {CLOCK};")]
                if card != "emmc":
                    controls.append(("top/monitor_interface.sv", "input wire link_card_clk;"))
                else:
                    kit = "component/kit_sequencer.sv"
                    rw = "sequence/test/rw.sv"
                    mutations = (
                        {kit: files[kit].replace("bit auto_clock_phase = 0", "bit auto_clock_phase = 1")},
                        {rw: files[rw].replace("2.0 * one_way_deg", "one_way_deg")},
                    )
                    for mutation in mutations:
                        try:
                            verify(files | mutation, controller, card, dma, clock)
                        except ValueError:
                            rejected += 1
                        else:
                            raise ValueError("generation check accepted an invalid link phase contract")
                for path, snippet in controls:
                    try:
                        verify(files | {path: files[path] + "\n" + snippet}, controller, card, dma, clock)
                    except ValueError:
                        rejected += 1
                    else:
                        raise ValueError(f"pruning check accepted a disabled feature in {path}")
    try:
        check_source("package type_only;\ntypedef int status_t;\nendpackage", "invalid.sv")
    except ValueError:
        rejected += 1
    else:
        raise ValueError("package policy accepted a type-only package")
    print(json.dumps({"passed": True, "family": FAMILY.relative_to(ROOT).as_posix(),
                      "profiles": reports, "compiled_profiles": len(reports), "rejected_controls": rejected}))


if __name__ == "__main__":
    main()

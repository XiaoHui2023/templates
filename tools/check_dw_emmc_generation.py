"""Check conditional DW eMMC products against their compile lists."""

from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tempfile

from check_dw_emmc_read import FAMILY
from check_sv_declaration_ownership import check_source, self_test
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
        for pin in ("phase_tx_ref", "phase_tx_clk", "phase_rx_ref", "phase_rx_clk"):
            if bool(re.search(rf"\binput wire {pin}\b", files[path])) != (card == "emmc"):
                raise ValueError(f"phase clock port disagrees with card type: {path}:{pin}")

    phase_argument = re.search(r"extern task rw_test\([^\n]*, bit auto_clock_phase = 0\);", kit)
    phase_route = "auto_clock_phase == local::auto_clock_phase;"
    expected_routes = 5 if card == "emmc" else 0
    if (bool(phase_argument) != (card == "emmc")
        or kit.count(phase_route) != int(card == "emmc")
        or files["sequence/test/rw.sv"].count(phase_route) != expected_routes):
        raise ValueError("incorrect rw_test phase switch default or route")
    phase_flow = files["sequence/flow/xfer/base.sv"]
    phase_before_io = re.search(
        r"::body\(\);\s*if \(auto_clock_phase\)\s*adjust_clock_phase\(\);\s*"
        r"(?:write_dma_descriptor\(\);\s*)?set_block_length\(\);\s*execute_command\(\);", phase_flow)
    if bool(phase_before_io) != (card == "emmc"):
        raise ValueError("phase adjustment must be optional and before launching I/O")
    if card != "emmc" and any(re.search(r"\b(?:auto_clock_phase|adjust_(?:clock|tx|rx)_phase)\b",
                                       files[path]) for path in sources):
        raise ValueError("phase code leaked outside eMMC")


def main():
    reports = {}
    rejected = 0
    self_test()
    executable = renderer()
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
            reports[name] = len(files)
            if not dma and not clock:
                controls = [("component/kit_sequencer.sv", "extern task dma_test();"),
                            ("top/interface.sv", f"input wire {CLOCK};")]
                if card != "emmc":
                    controls.append(("top/monitor_interface.sv", "input wire phase_rx_clk;"))
                else:
                    try:
                        verify(files | {"component/kit_sequencer.sv": kit_without_opt_in(files)},
                               controller, card, dma, clock)
                    except ValueError:
                        rejected += 1
                    else:
                        raise ValueError("generation check accepted opt-out phase adjustment")
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
                      "profiles": reports, "rejected_controls": rejected}))


def kit_without_opt_in(files):
    return files["component/kit_sequencer.sv"].replace("bit auto_clock_phase = 0", "bit auto_clock_phase = 1")


if __name__ == "__main__":
    main()

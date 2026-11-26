"""Check conditional DW eMMC products against their compile lists."""

from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tempfile

from check_dw_emmc_read import FAMILY, check_phase_package
from check_template_pruning import ROOT, renderer


CONTROLLERS = (("mshc", "emmc"), ("mshc", "sdcard"), ("mshc", "sdio"), ("mobile_storage", "sdio"))
DESCRIPTORS = {"mshc": "model/data/adma_des.sv", "mobile_storage": "model/data/idmac_descriptor.sv"}
DMA_TEST = "sequence/test/dma.sv"
CLOCK = "contract_clock"


def check_timed_packages(files):
    """Reject project packages used only as namespaces."""
    for path, source in files.items():
        if not path.endswith(".sv"):
            continue
        code = re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", source)
        for match in re.finditer(r"^\s*package\s+(\w+)\s*;(.*?)^\s*endpackage\b", code, re.M | re.S):
            name, body = match.groups()
            if (not re.search(r"\btimeunit\s+", body) or not re.search(r"\btimeprecision\s+", body)
                    or not re.search(r"#\s*\([^;]*\d(?:fs|ps|ns|us|ms|s)\b", body)):
                raise ValueError(f"{path}: {name} must own a timed procedure and declare its time scale")


def verify(files, controller, dma, clock):
    listed = [name for name in files["all.f"].splitlines() if name]
    sources = {path for path in files if path.endswith(".sv")}
    if len(listed) != len(sources) or set(listed) != sources:
        raise ValueError(f"incorrect all.f: missing={sorted(sources - set(listed))}, "
                         f"unbuilt={sorted(set(listed) - sources)}, repeated={len(listed) - len(set(listed))}")
    check_timed_packages(files)

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


def main():
    reports = {}
    rejected = 0
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
            check_phase_package(output)
            try:
                verify(files, controller, dma, clock)
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from error
            reports[name] = len(files)
            if not dma and not clock:
                for path, snippet in (("component/kit_sequencer.sv", "extern task dma_test();"),
                                      ("top/interface.sv", f"input wire {CLOCK};")):
                    try:
                        verify(files | {path: files[path] + "\n" + snippet}, controller, dma, clock)
                    except ValueError:
                        rejected += 1
                    else:
                        raise ValueError(f"pruning check accepted a disabled feature in {path}")
    try:
        check_timed_packages({"invalid.sv": "package type_only;\ntypedef int status_t;\nendpackage"})
    except ValueError:
        rejected += 1
    else:
        raise ValueError("package policy accepted a type-only package")
    print(json.dumps({"passed": True, "family": FAMILY.relative_to(ROOT).as_posix(),
                      "profiles": reports, "rejected_controls": rejected}))


if __name__ == "__main__":
    main()

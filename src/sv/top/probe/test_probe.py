from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import ValidationError

from models import Models


ROOT = Path(__file__).resolve().parent


def render_templates(model: Models) -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        undefined=StrictUndefined,
    )
    context = model.model_dump()
    rendered: dict[str, str] = {}
    for name in [
        "probe.f.j2",
        "path_macros.sv.j2",
        "probe_signal_if.sv.j2",
        "probe_if.sv.j2",
        "probe_check.sv.j2",
    ]:
        rendered[name] = env.get_template(name).render(**context)
    return rendered


def test_example_renders() -> None:
    data = yaml.safe_load((ROOT / "example.yaml").read_text(encoding="utf-8"))
    model = Models.model_validate(data)
    rendered = render_templates(model)

    assert rendered["probe.f.j2"].splitlines() == [
        "path_macros.sv",
        "probe_signal_if.sv",
        "probe_if.sv",
        "probe_check.sv",
    ]
    assert "`define PROBE_PATH_CPU_CLK dut.u_top.cpu_clk" in rendered["path_macros.sv.j2"]
    assert "interface probe_if;" in rendered["probe_if.sv.j2"]
    assert "probe_signal_if #(.FREQ(100000000)) cpu_clk" in rendered["probe_if.sv.j2"]
    assert "input virtual probe_if probe" in rendered["probe_check.sv.j2"]
    assert "output bit pass" in rendered["probe_check.sv.j2"]
    assert "bit signal_ok[2];" in rendered["probe_check.sv.j2"]
    assert "watchdog_timeout_ns" in rendered["probe_check.sv.j2"]
    assert "join_any" in rendered["probe_check.sv.j2"]
    assert "pass &= signal_ok[0];" in rendered["probe_check.sv.j2"]
    assert "pass &= signal_ok[1];" in rendered["probe_check.sv.j2"]
    assert ".TOLERANCE_PPM" not in rendered["probe_if.sv.j2"]
    assert ".MIN_FREQ_HZ" not in rendered["probe_if.sv.j2"]
    assert ".STABLE_CYCLES" not in rendered["probe_if.sv.j2"]


def test_omitted_freq_defaults_to_inactive() -> None:
    model = Models.model_validate(
        {
            "signals": {
                "sleep_clk": {
                    "path": "dut.u_top.sleep_clk",
                },
            },
        }
    )
    rendered = render_templates(model)

    assert model.signals["sleep_clk"].freq == 0
    assert "probe_signal_if #(.FREQ(0)) sleep_clk" in rendered["probe_if.sv.j2"]
    assert 'probe.sleep_clk.check("sleep_clk", signal_ok[0]);' in rendered["probe_check.sv.j2"]


def test_prefix_applies_to_global_symbols() -> None:
    model = Models.model_validate(
        {
            "signals": {
                "cpu_clk": {
                    "path": "dut.u_top.cpu_clk",
                    "freq": 100000000,
                },
            },
            "settings": {
                "prefix": "pll0_",
            },
        }
    )
    rendered = render_templates(model)

    assert "`define PLL0_PATH_CPU_CLK dut.u_top.cpu_clk" in rendered["path_macros.sv.j2"]
    assert "interface pll0_signal_if" in rendered["probe_signal_if.sv.j2"]
    assert "interface pll0_if;" in rendered["probe_if.sv.j2"]
    assert "pll0_signal_if #(.FREQ(100000000)) cpu_clk" in rendered["probe_if.sv.j2"]
    assert "input virtual pll0_if probe" in rendered["probe_check.sv.j2"]
    assert "output bit pass" in rendered["probe_check.sv.j2"]


def test_many_signals_render_as_parallel_checks() -> None:
    signal_count = 1000
    signals = {
        f"clk_{index}": {
            "path": f"dut.clk_{index}",
            "freq": 100000000,
        }
        for index in range(signal_count)
    }
    model = Models.model_validate({"signals": signals})
    rendered = render_templates(model)
    check_text = rendered["probe_check.sv.j2"]

    assert f"bit signal_ok[{signal_count}];" in check_text
    assert check_text.count(".check(") == signal_count
    assert check_text.count("pass &= signal_ok[") == signal_count
    assert check_text.count("watchdog_timeout_ns") == 5
    assert "wait_posedge_or_timeout" not in rendered["probe_signal_if.sv.j2"]
    assert "frequency_timeout_ns" in rendered["probe_signal_if.sv.j2"]
    assert "edge_period_ns() * STABLE_CYCLES" not in rendered["probe_signal_if.sv.j2"]


def test_unsupported_signal_fields_are_rejected() -> None:
    try:
        Models.model_validate(
            {
                "signals": {
                    "cpu_clk": {
                        "path": "dut.u_top.cpu_clk",
                        "source": "pll",
                    },
                },
            }
        )
    except ValidationError as exc:
        assert "source" in str(exc)
    else:
        raise AssertionError("unsupported signal field was accepted")

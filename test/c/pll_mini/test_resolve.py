from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PKG = Path(__file__).resolve().parents[3] / "src" / "c" / "pll_mini"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from models import Models  # noqa: E402


class ResolveTests(unittest.TestCase):
    def _load(self, yaml_name: str) -> Models:
        fixture_dir = Path(__file__).resolve().parent / "fixtures"
        import yaml

        data = yaml.safe_load(
            (fixture_dir / yaml_name).read_text(encoding="utf-8")
        )
        return Models.model_validate_with_yaml_dir(
            data, yaml_dir=fixture_dir
        )

    def test_single_clk_example(self) -> None:
        model = self._load("single_clk.yaml")
        resolved = model.tree_resolve
        self.assertEqual(resolved.clk_names, ("clk_out",))
        self.assertEqual(resolved.by_name["clk_out"].resolved_freq, 30_000_000)
        self.assertEqual(resolved.by_name["div0"].ratio, 2)
        self.assertEqual(resolved.by_name["mux_ref"].mux_sel, 0)
        plan = model.config_plan
        self.assertGreater(len(plan.pll_writes), 0)
        self.assertGreater(len(plan.dev_steps), 0)
        self.assertEqual(plan.fixed_wait_lock_mask_hex, "0x00000001u")

    def test_multi_clk_shared_pll(self) -> None:
        model = self._load("multi_clk.yaml")
        resolved = model.tree_resolve
        self.assertEqual(
            set(resolved.clk_names),
            {"clk_out", "clk_cpu"},
        )
        self.assertEqual(
            resolved.by_name["clk_out"].resolved_freq,
            30_000_000,
        )
        self.assertEqual(
            resolved.by_name["clk_cpu"].resolved_freq,
            60_000_000,
        )
        self.assertTrue(resolved.by_name["pll_sc"].active)
        self.assertEqual(resolved.by_name["div0"].ratio, 2)


if __name__ == "__main__":
    unittest.main()

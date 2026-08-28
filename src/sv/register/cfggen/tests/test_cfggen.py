from __future__ import annotations

import sys
import unittest
from pathlib import Path


FAMILY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FAMILY_DIR))

from cfggen_model import CfgDesignBuilder  # noqa: E402
from models import Models  # noqa: E402
from ralf_model import parse_ralf  # noqa: E402


class CfggenTest(unittest.TestCase):
    def test_example_normalizes_retained_field_range_and_orders_dependencies(self) -> None:
        design = Models(
            ralf_file=str(FAMILY_DIR / "example.ralf"),
            emit_ral_sync_methods=True,
        ).design

        self.assertEqual([item.class_name for item in design.registers], ["cfg_uart_ctrl"])
        register = design.registers[0]
        self.assertEqual(register.value_width, 7)
        self.assertEqual(register.reset_literal, "7'h31")
        self.assertEqual(
            [(field.name, field.value_msb, field.value_lsb) for field in register.fields],
            [("enable", 0, 0), ("mode", 6, 4)],
        )
        self.assertEqual(
            [item.class_name for item in design.containers],
            ["cfg_uart", "cfg_peripherals", "cfg_chip"],
        )

    def test_register_is_removed_when_every_field_access_is_ignored(self) -> None:
        document = parse_ralf(
            "block DEV { register STATUS @0 { field READY @0 { bits 1; access ro; } } }"
        )
        design = self._build(document)

        self.assertEqual(design.registers, [])
        self.assertEqual(design.containers[0].children, [])

    def test_unresolved_reference_is_rejected(self) -> None:
        document = parse_ralf("system TOP { block CHILD = MISSING; }")

        with self.assertRaisesRegex(ValueError, "unresolved block reference"):
            self._build(document)

    def test_field_collision_with_fixed_member_is_rejected(self) -> None:
        document = parse_ralf(
            "block DEV { register CTRL @0 { field VALUE @0 { bits 1; access rw; } } }"
        )

        with self.assertRaisesRegex(ValueError, "collides with a generated register member"):
            self._build(document)

    def test_configurable_generated_names_must_be_unique(self) -> None:
        document = parse_ralf(
            "block DEV { register CTRL @0 { field ENABLE @0 { bits 1; access rw; } } }"
        )

        with self.assertRaisesRegex(ValueError, "generated register member names must be unique"):
            CfgDesignBuilder(
                document,
                class_prefix="cfg_",
                base_class="uvm_sequence_item",
                ignored_field_accesses={"ro"},
                emit_ral_sync_methods=False,
                value_name="value",
                rand_mode_lock_name="value",
                reset_value_name="reset_value",
                constraint_name="_cst",
                set_ral_method_name="set_ral_value",
                get_ral_method_name="get_ral_value",
            ).build()

    @staticmethod
    def _build(document):
        return CfgDesignBuilder(
            document,
            class_prefix="cfg_",
            base_class="uvm_sequence_item",
            ignored_field_accesses={"ro"},
            emit_ral_sync_methods=False,
            value_name="value",
            rand_mode_lock_name="rand_mode_locked",
            reset_value_name="reset_value",
            constraint_name="_cst",
            set_ral_method_name="set_ral_value",
            get_ral_method_name="get_ral_value",
        ).build()


if __name__ == "__main__":
    unittest.main()

import unittest
from decimal import Decimal

from bluetti_bt_lib.devices.el10 import EL10
from bluetti_bt_lib.fields import DecimalField

# Selects the device is slow to reflect back after a write.
SLOW_SELECTS = (
    "ctrl_eco_time_mode_dc",
    "ctrl_eco_time_mode_ac",
    "ctrl_charging_mode",
    "ctrl_display_timeout",
)


class TestEL10(unittest.TestCase):
    def setUp(self):
        self.device = EL10()

    def _field(self, name):
        return next(f for f in self.device.fields if f.name == name)

    def test_discharge_time_remaining_reads_hours(self):
        # Register 105 counts minutes; report it in hours like the charge
        # counterpart at 104 (time_remaining).
        field = self._field("discharge_time_remaining")
        self.assertIsInstance(field, DecimalField)
        self.assertEqual(field.address, 105)
        self.assertEqual(field.parse(b"\x00\x5a"), Decimal("1.5"))

    def test_time_remaining_keeps_its_hours_scale(self):
        self.assertEqual(
            self._field("time_remaining").parse(b"\x00\x5a"), Decimal("1.5")
        )

    def test_slow_selects_declare_verification_delay(self):
        for name in SLOW_SELECTS:
            with self.subTest(field=name):
                self.assertEqual(self._field(name).verification_delay, 2.0)

    def test_no_ups_controls(self):
        # The small power station has no UPS register map.
        for name in ("ctrl_ups_mode", "ctrl_grid_charge_on"):
            with self.subTest(field=name):
                self.assertFalse(any(f.name == name for f in self.device.fields))


if __name__ == "__main__":
    unittest.main()

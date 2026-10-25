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

    def test_time_remaining_reads_hours(self):
        field = self._field("time_remaining")
        self.assertIsInstance(field, DecimalField)
        self.assertEqual(field.address, 104)
        self.assertEqual(field.parse(b"\x00\x5a"), Decimal("1.5"))

    def test_register_105_is_not_exposed(self):
        # 105 mirrors the charge time at 104, so it is not a separate sensor.
        self.assertFalse(any(f.address == 105 for f in self.device.fields))

    def test_selects_take_the_default_verification_window(self):
        for name in SLOW_SELECTS:
            with self.subTest(field=name):
                self.assertIsNone(self._field(name).verification_delay)

    def test_no_ups_controls(self):
        # The small power station has no UPS register map.
        for name in ("ctrl_ups_mode", "ctrl_grid_charge_on"):
            with self.subTest(field=name):
                self.assertFalse(any(f.name == name for f in self.device.fields))


if __name__ == "__main__":
    unittest.main()

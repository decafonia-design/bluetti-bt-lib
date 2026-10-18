import unittest
from decimal import Decimal

from bluetti_bt_lib.devices.el100v2 import EL100V2
from bluetti_bt_lib.enums import WorkingModeV2
from bluetti_bt_lib.fields import DecimalField, SelectField, SwitchField

# Selects the device is slow to reflect back after a write.
SLOW_SELECTS = (
    "ctrl_eco_time_mode_dc",
    "ctrl_eco_time_mode_ac",
    "ctrl_charging_mode",
    "ctrl_display_timeout",
)


class TestEL100V2(unittest.TestCase):
    def setUp(self):
        self.device = EL100V2()

    def _field(self, name):
        return next(f for f in self.device.fields if f.name == name)

    def test_ups_mode_uses_v2_working_mode_values(self):
        # The V2 portables hold the UPS mode at 2005, with different values
        # than the V1 UpsMode register (3001).
        ups = self._field("ctrl_ups_mode")
        self.assertIsInstance(ups, SelectField)
        self.assertEqual(ups.address, 2005)
        self.assertIs(ups.e, WorkingModeV2)
        self.assertEqual(ups.verification_delay, 2.0)

        self.assertEqual(
            self.device.build_write_command("ctrl_ups_mode", "STANDARD").value, 4
        )
        self.assertEqual(
            self.device.build_write_command("ctrl_ups_mode", "TIME_CONTROL").value, 5
        )

    def test_ups_mode_rejects_v1_only_values(self):
        # 3 is UpsMode.STANDARD on V1 but is not a valid value on 2005.
        self.assertIsNone(self._field("ctrl_ups_mode").parse(b"\x00\x03"))
        self.assertEqual(
            self._field("ctrl_ups_mode").parse(b"\x00\x04"), WorkingModeV2.STANDARD
        )

    def test_grid_charge_switch_is_at_2008(self):
        # Same function as the AC300's ctrl_grid_charge_on, different register.
        grid = self._field("ctrl_grid_charge_on")
        self.assertIsInstance(grid, SwitchField)
        self.assertEqual(grid.address, 2008)
        self.assertTrue(grid.is_writeable())

        command = self.device.build_write_command("ctrl_grid_charge_on", True)
        self.assertEqual((command.address, command.value), (2008, 1))

    def test_discharge_time_remaining_reads_hours(self):
        # Register 105 counts minutes; report it in hours like the charge
        # counterpart at 104 (time_remaining).
        field = self._field("discharge_time_remaining")
        self.assertIsInstance(field, DecimalField)
        self.assertEqual(field.address, 105)
        self.assertEqual(field.parse(b"\x00\x5a"), Decimal("1.5"))

    def test_slow_selects_declare_verification_delay(self):
        for name in SLOW_SELECTS:
            with self.subTest(field=name):
                self.assertEqual(self._field(name).verification_delay, 2.0)

    def test_soc_range_keeps_verification_delay(self):
        self.assertEqual(self._field("soc_range_start").verification_delay, 2.0)
        self.assertEqual(self._field("soc_range_end").verification_delay, 2.0)


if __name__ == "__main__":
    unittest.main()

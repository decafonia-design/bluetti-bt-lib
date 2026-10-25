import unittest

from bluetti_bt_lib.devices.ac500 import AC500
from bluetti_bt_lib.fields import SwitchField

# Same controls the AC300 exposes, at the same registers.
GRID_SWITCHES = {
    "ctrl_grid_charge_on": 3011,
    "ctrl_time_control_on": 3013,
}


class TestAC500(unittest.TestCase):
    def setUp(self):
        self.device = AC500()

    def _field(self, name):
        return next(f for f in self.device.fields if f.name == name)

    def test_grid_switches_match_the_ac300(self):
        for name, address in GRID_SWITCHES.items():
            with self.subTest(field=name):
                field = self._field(name)
                self.assertIsInstance(field, SwitchField)
                self.assertEqual(field.address, address)
                self.assertTrue(field.is_writeable())

    def test_grid_switches_write_on_off(self):
        for name, address in GRID_SWITCHES.items():
            with self.subTest(field=name):
                on = self.device.build_write_command(name, True)
                off = self.device.build_write_command(name, False)
                self.assertEqual((on.address, on.value), (address, 1))
                self.assertEqual((off.address, off.value), (address, 0))

    def test_selects_take_the_default_verification_window(self):
        for name in ("ctrl_ups_mode", "ctrl_display_timeout"):
            with self.subTest(field=name):
                self.assertIsNone(self._field(name).verification_delay)


if __name__ == "__main__":
    unittest.main()

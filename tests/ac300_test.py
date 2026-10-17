import unittest

from bluetti_bt_lib.devices.ac300 import AC300
from bluetti_bt_lib.fields import NumberField


class TestAC300(unittest.TestCase):
    def setUp(self):
        self.device = AC300()

    def test_pack_fields_trimmed_to_soc(self):
        # Only the per-pack SOC should remain; the read-only selected,
        # voltage and 16 cell-voltage fields are dropped.
        self.assertEqual([f.name for f in self.device.pack_fields], ["battery_soc"])
        self.assertEqual(self.device.max_packs, 4)

    def test_soc_range_is_writable_number(self):
        start = next(
            f for f in self.device.fields if f.name == "soc_range_start"
        )
        end = next(f for f in self.device.fields if f.name == "soc_range_end")
        self.assertIsInstance(start, NumberField)
        self.assertIsInstance(end, NumberField)
        self.assertTrue(start.is_writeable())
        self.assertTrue(end.is_writeable())
        self.assertEqual(start.step, 5)
        self.assertEqual(end.step, 5)

        self.assertEqual(self.device.build_write_command("soc_range_start", 30).value, 30)
        self.assertEqual(self.device.build_write_command("soc_range_end", 90).value, 90)

    def test_soc_range_rejects_off_step_values(self):
        # 5% increments: off-step values must be rejected so a service
        # call cannot bypass the intended increments.
        self.assertIsNone(self.device.build_write_command("soc_range_start", 32))
        self.assertIsNone(self.device.build_write_command("soc_range_end", 91))

    def test_soc_range_rejects_out_of_range_and_bool(self):
        self.assertIsNone(self.device.build_write_command("soc_range_start", 150))
        self.assertIsNone(self.device.build_write_command("soc_range_start", -1))
        self.assertIsNone(self.device.build_write_command("soc_range_start", True))

    def test_ups_switches_present_and_writable(self):
        names = {f.name for f in self.device.get_switch_fields()}
        self.assertIn("ctrl_grid_charge_on", names)
        self.assertIn("ctrl_time_control_on", names)

        self.assertEqual(self.device.build_write_command("ctrl_grid_charge_on", True).address, 3011)
        self.assertEqual(self.device.build_write_command("ctrl_time_control_on", False).address, 3013)


if __name__ == "__main__":
    unittest.main()

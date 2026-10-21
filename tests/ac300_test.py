import unittest

from bluetti_bt_lib.devices.ac300 import AC300
from bluetti_bt_lib.fields import NumberField


class TestAC300(unittest.TestCase):
    def setUp(self):
        self.device = AC300()

    def test_pack_fields_trimmed_to_voltage_and_soc(self):
        # The per-pack voltage and SOC stay; the read-only selected flag and
        # the 16 cell-voltage fields are dropped.
        self.assertEqual(
            [f.name for f in self.device.pack_fields], ["voltage", "battery_soc"]
        )
        self.assertEqual([f.address for f in self.device.pack_fields], [98, 99])
        self.assertEqual(self.device.max_packs, 4)

    def test_power_generation_reads_register_41(self):
        # Register 41 is the generated-energy counter (kWh, only ever
        # increasing). Register 43 is the SOC: reading it as
        # power_generation made the sensor track stored energy and
        # decrease on discharge, breaking HA's total_increasing state
        # class.
        gen = next(
            f for f in self.device.fields if f.name == "power_generation"
        )
        self.assertEqual(gen.address, 41)

    def test_polling_blocks(self):
        # One request per field put the AC300 at 28 reads plus two per pack
        # slot, which is most of a poll cycle on the radio. Neighbouring
        # main registers are read together instead; the pack reads stay as
        # they were.
        blocks = self.device.get_polling_registers()
        self.assertEqual(len(blocks), 7)

        # The identity and firmware registers are not part of the cycle; they
        # are read once per connection (see STARTUP_FIELDS).
        startup = self.device.get_startup_registers()
        self.assertEqual(len(startup), 2)
        self.assertEqual(startup[0].starting_address, 10)
        self.assertEqual(startup[1].starting_address, 17)

        pack_blocks = self.device.get_pack_polling_registers()
        self.assertEqual(len(pack_blocks), 2)
        self.assertEqual(pack_blocks[0].starting_address, 98)
        self.assertEqual(pack_blocks[0].quantity, 1)
        self.assertEqual(pack_blocks[1].starting_address, 99)
        self.assertEqual(pack_blocks[1].quantity, 1)

    def test_soc_range_slow_verification_delay(self):
        # The SOC range thresholds are slow to reflect in their register,
        # so they declare the longer write-verification delay.
        start = next(
            f for f in self.device.fields if f.name == "soc_range_start"
        )
        end = next(f for f in self.device.fields if f.name == "soc_range_end")
        self.assertEqual(start.verification_delay, 2.0)
        self.assertEqual(end.verification_delay, 2.0)

    def test_soc_range_is_writable_number(self):
        start = next(
            f for f in self.device.fields if f.name == "soc_range_start"
        )
        end = next(f for f in self.device.fields if f.name == "soc_range_end")
        self.assertIsInstance(start, NumberField)
        self.assertIsInstance(end, NumberField)
        self.assertTrue(start.is_writeable())
        self.assertTrue(end.is_writeable())
        self.assertEqual(start.step, 1)
        self.assertEqual(end.step, 1)

        self.assertEqual(self.device.build_write_command("soc_range_start", 30).value, 30)
        self.assertEqual(self.device.build_write_command("soc_range_end", 90).value, 90)

    def test_soc_range_accepts_off_step_values(self):
        # step is the increment we advertise to clients, not a hardware
        # limit: the device accepts 1%, so off-step values must write.
        self.assertEqual(
            self.device.build_write_command("soc_range_start", 32).value, 32
        )
        self.assertEqual(
            self.device.build_write_command("soc_range_end", 91).value, 91
        )

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

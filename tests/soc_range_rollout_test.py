import unittest

from bluetti_bt_lib.devices.ac200l import AC200L
from bluetti_bt_lib.devices.ac300 import AC300
from bluetti_bt_lib.devices.ac500 import AC500
from bluetti_bt_lib.devices.ap300 import AP300
from bluetti_bt_lib.devices.el100mini import EL100mini
from bluetti_bt_lib.devices.el100v2 import EL100V2
from bluetti_bt_lib.devices.el200v2 import EL200V2
from bluetti_bt_lib.devices.ep2000 import EP2000
from bluetti_bt_lib.devices.ep500 import EP500
from bluetti_bt_lib.devices.ep500p import EP500P
from bluetti_bt_lib.devices.ep600 import EP600
from bluetti_bt_lib.fields import NumberField

# Device class -> the SOC range register pair that device actually uses.
# The control mechanism (writable NumberField, 0-100, slow verification)
# is shared; the register locations stay device specific.
SOC_RANGE_REGISTERS = {
    AC300: (3015, 3016),
    AC500: (3015, 3016),
    AC200L: (3015, 3016),
    EP500: (3015, 3016),
    EP500P: (3015, 3016),
    AP300: (2022, 2023),
    EL100V2: (2022, 2023),
    EL200V2: (2022, 2023),
    EL100mini: (2022, 2023),
    EP600: (2022, 2023),
    EP2000: (2022, 2023),
}


class TestSocRangeRollout(unittest.TestCase):
    def _fields(self, device_cls):
        device = device_cls()
        start = next(f for f in device.fields if f.name == "soc_range_start")
        end = next(f for f in device.fields if f.name == "soc_range_end")
        return device, start, end

    def test_every_profile_uses_writable_number_field(self):
        for device_cls in SOC_RANGE_REGISTERS:
            with self.subTest(device=device_cls.__name__):
                _, start, end = self._fields(device_cls)
                self.assertIsInstance(start, NumberField)
                self.assertIsInstance(end, NumberField)
                self.assertTrue(start.is_writeable())
                self.assertTrue(end.is_writeable())

    def test_every_profile_keeps_its_own_registers(self):
        for device_cls, (start_addr, end_addr) in SOC_RANGE_REGISTERS.items():
            with self.subTest(device=device_cls.__name__):
                _, start, end = self._fields(device_cls)
                self.assertEqual(start.address, start_addr)
                self.assertEqual(end.address, end_addr)

    def test_every_profile_shares_the_ac300_limits_and_delay(self):
        for device_cls in SOC_RANGE_REGISTERS:
            with self.subTest(device=device_cls.__name__):
                _, start, end = self._fields(device_cls)
                for field in (start, end):
                    self.assertEqual(field.multiplier, 1)
                    self.assertEqual(field.min, 0)
                    self.assertEqual(field.max, 100)
                    self.assertEqual(field.step, 5)
                    self.assertEqual(field.verification_delay, 2.0)

    def test_write_commands_build_for_every_profile(self):
        for device_cls, (start_addr, end_addr) in SOC_RANGE_REGISTERS.items():
            with self.subTest(device=device_cls.__name__):
                device, _, _ = self._fields(device_cls)
                start = device.build_write_command("soc_range_start", 30)
                end = device.build_write_command("soc_range_end", 90)
                self.assertEqual((start.address, start.value), (start_addr, 30))
                self.assertEqual((end.address, end.value), (end_addr, 90))

    def test_off_step_writes_allowed_but_out_of_range_rejected(self):
        # step is a presentation hint; the devices accept 1% increments.
        # Only the 0-100 bounds and the non-int/bool guards reject a write.
        for device_cls in SOC_RANGE_REGISTERS:
            with self.subTest(device=device_cls.__name__):
                device, _, _ = self._fields(device_cls)
                self.assertEqual(
                    device.build_write_command("soc_range_start", 32).value, 32
                )
                self.assertEqual(
                    device.build_write_command("soc_range_end", 91).value, 91
                )
                self.assertIsNone(device.build_write_command("soc_range_start", 150))
                self.assertIsNone(device.build_write_command("soc_range_start", -1))
                self.assertIsNone(device.build_write_command("soc_range_start", True))


if __name__ == "__main__":
    unittest.main()

import unittest

from bluetti_bt_lib.devices.ac50b import AC50B

# The AC50B keeps its power readings in a block of pairs rather than the
# shared registers the other stations use.
POWER_REGISTERS = {
    "dc_output_power": 140,
    "ac_output_power": 142,
    "dc_input_power": 144,
    "ac_input_power": 146,
}


class TestAC50B(unittest.TestCase):
    def setUp(self):
        self.device = AC50B()

    def test_power_registers_are_read(self):
        fields = {f.name: f for f in self.device.fields}
        for name, address in POWER_REGISTERS.items():
            with self.subTest(field=name):
                self.assertEqual(fields[name].address, address)


if __name__ == "__main__":
    unittest.main()

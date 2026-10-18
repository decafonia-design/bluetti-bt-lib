import unittest

from bluetti_bt_lib.devices.handsfree1 import Handsfree1
from bluetti_bt_lib.devices.handsfree2 import Handsfree2


class TestHandsfree1(unittest.TestCase):
    def setUp(self):
        self.device = Handsfree1()

    def test_output_switches_match_handsfree2(self):
        # The Handsfree 1 shares the V2 output control registers with the
        # Handsfree 2 (and the rest of the V2 family).
        for device in (self.device, Handsfree2()):
            switches = {f.name: f.address for f in device.get_switch_fields()}
            self.assertEqual(switches.get("ctrl_ac"), 2011)
            self.assertEqual(switches.get("ctrl_dc"), 2012)

    def test_output_switches_are_writable(self):
        command = self.device.build_write_command("ctrl_ac", False)
        self.assertEqual((command.address, command.value), (2011, 0))


if __name__ == "__main__":
    unittest.main()

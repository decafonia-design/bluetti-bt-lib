import unittest

from bluetti_bt_lib.utils.device_builder import build_device
from bluetti_bt_lib.devices.el100v2 import EL100V2
from bluetti_bt_lib.devices.el200v2 import EL200V2


def _field_signature(device):
    return [(f.name, f.address) for f in device.fields]


class TestEL200V2(unittest.TestCase):
    def setUp(self):
        self.device = EL200V2()

    def test_it_is_a_clone_of_the_el100v2_profile(self):
        # The EL200V2 shares the Elite V2 register map, so the profiles are
        # expected to stay identical apart from the class name.
        self.assertEqual(_field_signature(self.device), _field_signature(EL100V2()))

    def test_it_builds_from_a_device_name(self):
        device = build_device("EL200V22539111584127")
        self.assertIsInstance(device, EL200V2)

    def test_shared_controls_are_writeable(self):
        for name in ("ctrl_ups_mode", "ctrl_grid_charge_on", "ctrl_charging_mode"):
            with self.subTest(field=name):
                field = next(f for f in self.device.fields if f.name == name)
                self.assertTrue(field.is_writeable())


if __name__ == "__main__":
    unittest.main()

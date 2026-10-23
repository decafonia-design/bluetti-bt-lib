import unittest

from bluetti_bt_lib.devices import DEVICES, DEVICE_ALIASES
from bluetti_bt_lib.utils.device_builder import build_device


class TestDeviceBuilder(unittest.TestCase):
    def test_build(self):
        for name, cls in DEVICES.items():
            built = build_device(name + "12345678")
            self.assertIsInstance(built, cls)

    def test_aliases_build_the_canonical_device(self):
        for alias, canonical in DEVICE_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIn(canonical, DEVICES)
                built = build_device(alias + "12345678")
                self.assertIsInstance(built, DEVICES[canonical])

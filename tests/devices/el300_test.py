import unittest

from bluetti_bt_lib.devices import EL100V2, EL200V2, EL300, EL30V2
from bluetti_bt_lib.utils.device_builder import build_device

# These portables share one register map, so their device files are kept as
# copies of the same layout. The copies stay unified on purpose; this test
# fails if one of them drifts away from the others.
UNIFIED_LAYOUT_DEVICES = (EL100V2, EL200V2, EL300, EL30V2)


def _layout(device_cls):
    device = device_cls()
    return [(f.name, f.address, f.size) for f in device.fields]


class TestEL300(unittest.TestCase):
    def test_builds_from_advertisement_name(self):
        self.assertIsInstance(build_device("EL30012345678"), EL300)

    def test_layout_matches_the_other_unified_portables(self):
        reference = _layout(EL100V2)
        for device_cls in UNIFIED_LAYOUT_DEVICES:
            with self.subTest(device=device_cls.__name__):
                self.assertEqual(_layout(device_cls), reference)

    def test_soc_range_and_ups_mode_use_the_v2_registers(self):
        device = EL300()
        addresses = {f.name: f.address for f in device.fields}
        self.assertEqual(addresses["ctrl_ups_mode"], 2005)
        self.assertEqual(addresses["ctrl_grid_charge_on"], 2008)
        self.assertEqual(addresses["soc_range_start"], 2022)
        self.assertEqual(addresses["soc_range_end"], 2023)


if __name__ == "__main__":
    unittest.main()

import unittest

from bluetti_bt_lib.devices import EL100V2, EL200V2, EL300, EL30V2
from bluetti_bt_lib.utils.device_builder import build_device

# These portables share one register map, so their device files are kept as
# copies of the same layout. The copies stay unified on purpose; this test
# fails if one of them drifts away from the others. It compares addresses
# rather than field types, so a register can be writable on one model without
# breaking the others.
UNIFIED_LAYOUT_DEVICES = (EL100V2, EL200V2, EL300)
# The EL30 V2 shares that map except for the working mode. Register 2005 is
# verified on the other portables, but an EL30 V2 owner saw it read 4 (time
# control) while the app showed Standard, so that profile leaves it out
# rather than offering a dropdown that could write the wrong mode to a UPS.
EL30V2_ONLY_DIFFERENCE = ("ctrl_ups_mode", 2005, 1)


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

    def test_el30v2_differs_only_by_the_working_mode(self):
        reference = set(_layout(EL100V2))
        el30v2 = set(_layout(EL30V2))

        self.assertEqual(reference - el30v2, {EL30V2_ONLY_DIFFERENCE})
        self.assertEqual(el30v2 - reference, set())

    def test_soc_range_and_ups_mode_use_the_v2_registers(self):
        device = EL300()
        addresses = {f.name: f.address for f in device.fields}
        self.assertEqual(addresses["ctrl_ups_mode"], 2005)
        self.assertEqual(addresses["ctrl_grid_charge_on"], 2008)
        self.assertEqual(addresses["soc_range_start"], 2022)
        self.assertEqual(addresses["soc_range_end"], 2023)
        self.assertEqual(addresses["ac_output_voltage"], 1431)

    def test_eco_thresholds_are_only_writable_on_the_el100v2(self):
        # The 5-20 W / 10-40 W ranges came from an owner's app on an EL100 V2.
        # The rest of the family keeps the read-only sensors until someone with
        # one confirms their app offers the same settings.
        for device_cls in (EL200V2, EL300, EL30V2):
            with self.subTest(device=device_cls.__name__):
                fields = {f.name: f for f in device_cls().fields}
                for name in ("ctrl_eco_min_power_dc", "ctrl_eco_min_power_ac"):
                    self.assertFalse(fields[name].is_writeable(), name)


if __name__ == "__main__":
    unittest.main()

from decimal import Decimal
import struct
import unittest

from bluetti_bt_lib.devices import EL100V2, EL200V2, EL300, EL30V2
from bluetti_bt_lib.enums import BatteryStatus, WorkingModeV2alt
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
# Fields read and checked on an owner's Elite 300 only (register dump of
# 25 Oct 2026). They stay off the other portables until someone verifies them
# there: the scale of the battery current already differs from what other
# projects give for the Elite 200 V2.
EL300_ONLY_FIELDS = {
    ("battery_voltage", 100, 1),
    ("battery_current", 101, 1),
    ("battery_status", 103, 1),
    ("time_to_empty", 105, 1),
    ("dc_output_energy", 150, 1),
    ("ac_output_energy", 152, 1),
    ("dc_input_energy", 154, 1),
    ("ac_input_energy", 156, 1),
    ("battery_soh", 6006, 1),
    ("battery_temperature", 6007, 1),
}


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
                layout = _layout(device_cls)
                if device_cls is EL300:
                    self.assertTrue(EL300_ONLY_FIELDS <= set(layout))
                    layout = [f for f in layout if f not in EL300_ONLY_FIELDS]
                self.assertEqual(layout, reference)

    def _parse(self, name, raw):
        field = next(f for f in EL300().fields if f.name == name)
        value = field.parse(struct.pack("!H", raw))
        return value, field.in_range(value)

    def test_battery_values_from_an_owners_dump(self):
        self.assertEqual(self._parse("battery_voltage", 996), (Decimal("99.6"), True))
        self.assertEqual(self._parse("battery_current", 7), (Decimal("0.07"), True))
        self.assertEqual(self._parse("battery_current", 0xFFF9)[0], Decimal("-0.07"))
        self.assertEqual(self._parse("battery_status", 0)[0], BatteryStatus.IDLE)
        self.assertEqual(self._parse("battery_soh", 100), (100, True))
        self.assertEqual(self._parse("battery_temperature", 54), (14, True))
        self.assertEqual(self._parse("battery_temperature", 30), (-10, True))
        self.assertFalse(self._parse("battery_temperature", 404)[1])

    def test_lifetime_energy_in_tenths_of_a_kwh(self):
        self.assertEqual(self._parse("dc_output_energy", 4)[0], Decimal("0.4"))
        self.assertEqual(self._parse("ac_output_energy", 65)[0], Decimal("6.5"))
        self.assertEqual(self._parse("dc_input_energy", 74)[0], Decimal("7.4"))
        self.assertEqual(self._parse("ac_input_energy", 56)[0], Decimal("5.6"))

    def test_time_to_empty_in_hours(self):
        value, _ = self._parse("time_to_empty", 30269)
        self.assertEqual(round(value, 2), Decimal("504.48"))

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

    def test_ups_mode_reads_customized_as_3(self):
        # An owner's Elite 300 reads 3 at 2005 while the BLUETTI app and the
        # official integration show Customized UPS.
        field = next(f for f in EL300().fields if f.name == "ctrl_ups_mode")
        self.assertEqual(
            field.parse(struct.pack("!H", 3)), WorkingModeV2alt.CUSTOMIZED
        )

    def test_ups_mode_leaves_unseen_values_unknown(self):
        # 1, 2, 4 and 5 are the other modes on the V2 portables; on the
        # Elite 300 none of them has been seen yet, so none may be read as a
        # mode.
        field = next(f for f in EL300().fields if f.name == "ctrl_ups_mode")
        for value in (1, 2, 4, 5):
            with self.subTest(value=value):
                self.assertIsNone(field.parse(struct.pack("!H", value)))


if __name__ == "__main__":
    unittest.main()

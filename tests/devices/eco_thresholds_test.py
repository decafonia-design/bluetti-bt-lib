import unittest

from bluetti_bt_lib.devices import (
    AC70,
    AC180,
    AP300,
    EL10,
    EL100mini,
    EL100V2,
    EL200V2,
    EL300,
    EL30V2,
)

# Registers 2016 and 2019 hold the DC and AC eco auto-off thresholds. The app
# only lets the owner set them on some models, and the ranges it offers differ,
# so each confirmed range is recorded here as (dc_min, dc_max, ac_min, ac_max).
APP_VERIFIED = {
    EL100V2: (5, 20, 10, 40),
    AP300: (5, 20, 10, 40),
    EL100mini: (5, 20, 10, 40),
    EL10: (5, 10, 15, 30),
}

# The same registers are readable on these, but no owner has confirmed their
# app offers the settings, so they stay read-only sensors rather than a slider
# that could write a value the station ignores.
READ_ONLY = (EL200V2, EL300, EL30V2, AC70, AC180)

# The registers hold whole watts, so the sliders move in 1 W steps.
STEP = 1


class TestEcoThresholds(unittest.TestCase):
    def _eco_fields(self, device_cls):
        fields = {f.name: f for f in device_cls().fields}
        return fields["ctrl_eco_min_power_dc"], fields["ctrl_eco_min_power_ac"]

    def test_confirmed_ranges_are_writable(self):
        for device_cls, (dc_min, dc_max, ac_min, ac_max) in APP_VERIFIED.items():
            with self.subTest(device=device_cls.__name__):
                dc, ac = self._eco_fields(device_cls)

                self.assertEqual(
                    (dc.address, dc.min, dc.max, dc.step), (2016, dc_min, dc_max, STEP)
                )
                self.assertEqual(
                    (ac.address, ac.min, ac.max, ac.step), (2019, ac_min, ac_max, STEP)
                )
                self.assertTrue(dc.is_writeable())
                self.assertTrue(ac.is_writeable())

    def test_writes_inside_the_range_are_built(self):
        for device_cls, (_dc_min, _dc_max, ac_min, ac_max) in APP_VERIFIED.items():
            with self.subTest(device=device_cls.__name__):
                device = device_cls()
                value = ac_min + STEP
                self.assertLessEqual(value, ac_max)

                command = device.build_write_command("ctrl_eco_min_power_ac", value)
                self.assertEqual((command.address, command.value), (2019, value))

    def test_writes_outside_the_range_are_refused(self):
        for device_cls, (_dc_min, dc_max, _ac_min, ac_max) in APP_VERIFIED.items():
            with self.subTest(device=device_cls.__name__):
                device = device_cls()
                self.assertIsNone(
                    device.build_write_command("ctrl_eco_min_power_dc", dc_max + 5)
                )
                self.assertIsNone(
                    device.build_write_command("ctrl_eco_min_power_ac", ac_max + 5)
                )

    def test_unconfirmed_models_stay_read_only(self):
        for device_cls in READ_ONLY:
            with self.subTest(device=device_cls.__name__):
                dc, ac = self._eco_fields(device_cls)
                self.assertFalse(dc.is_writeable())
                self.assertFalse(ac.is_writeable())


if __name__ == "__main__":
    unittest.main()

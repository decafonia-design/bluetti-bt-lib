import unittest

from bluetti_bt_lib.devices import AC200M, AC300, AC500
from bluetti_bt_lib.fields import DecimalField

# The AC300 is the reference tower profile: it is the one tested against
# bt-lib hardware, so the AC500 (same functions) and the AC200M (a smaller
# station without the UPS feature set) are held to it.
REFERENCE = AC300
OTHER_TOWERS = (AC500, AC200M)

# The AC200M has no UPS, no split-phase output and no time-of-use
# programming, so these AC300/AC500 controls must stay off its profile.
AC200M_OMITS = (
    "ctrl_ups_mode",
    "ctrl_split_phase",
    "ctrl_split_phase_mode",
    "ctrl_grid_charge_on",
    "ctrl_time_control_on",
    "soc_range_start",
    "soc_range_end",
)


class TestACTowers(unittest.TestCase):
    def _fields(self, device_type):
        return {field.name: field for field in device_type().fields}

    def test_all_towers_report_versions_and_generated_energy(self):
        for device_type in (AC300, AC500, AC200M):
            fields = self._fields(device_type)
            with self.subTest(device=device_type.__name__):
                self.assertEqual(fields["version_arm"].address, 23)
                self.assertEqual(fields["version_dsp"].address, 25)
                self.assertEqual(fields["power_generation"].address, 41)

    def test_shared_registers_match_the_ac300(self):
        base = self._fields(REFERENCE)
        for device_type in OTHER_TOWERS:
            fields = self._fields(device_type)
            for name, field in sorted(base.items()):
                if name not in fields:
                    continue
                with self.subTest(device=device_type.__name__, field=name):
                    self.assertEqual(fields[name].address, field.address)
                    self.assertEqual(fields[name].size, field.size)

    def test_ac500_scaling_matches_the_ac300(self):
        # The AC500 is two AC300 towers, so a shared register decodes the
        # same way on both.
        base = self._fields(REFERENCE)
        fields = self._fields(AC500)
        for name, field in sorted(base.items()):
            if not isinstance(field, DecimalField) or name not in fields:
                continue
            other = fields[name]
            with self.subTest(field=name):
                self.assertEqual(other.scale, field.scale)
                self.assertEqual(other.multiplier, field.multiplier)

    def test_ac200m_omits_the_ups_and_split_phase_controls(self):
        fields = self._fields(AC200M)
        for name in AC200M_OMITS:
            with self.subTest(field=name):
                self.assertNotIn(name, fields)

    def test_ac500_keeps_the_ups_and_split_phase_controls(self):
        fields = self._fields(AC500)
        for name in AC200M_OMITS:
            with self.subTest(field=name):
                self.assertIn(name, fields)

    def test_pack_fields_match_across_the_towers(self):
        for device_type in (AC300, AC500, AC200M):
            device = device_type()
            with self.subTest(device=device_type.__name__):
                self.assertEqual(
                    [f.name for f in device.pack_fields], ["voltage", "battery_soc"]
                )
                self.assertEqual([f.address for f in device.pack_fields], [98, 99])
                self.assertGreater(device.max_packs, 0)


if __name__ == "__main__":
    unittest.main()

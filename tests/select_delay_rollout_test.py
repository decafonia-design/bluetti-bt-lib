import unittest

from bluetti_bt_lib.devices import DEVICES
from bluetti_bt_lib.fields import SelectField

# SelectField used to carry a longer verification delay of its own because the
# old write check was a single read-back after a fixed pause. The writer now
# retries the read-back across a window, which covers a station that is slow to
# reflect a select, so a select only declares a delay when its profile has a
# specific reason to.


class TestSelectDelayRollout(unittest.TestCase):
    def _selects(self, device_cls):
        return [f for f in device_cls().fields if isinstance(f, SelectField)]

    def test_every_select_takes_the_default_verification_window(self):
        for device_name, device_cls in DEVICES.items():
            for field in self._selects(device_cls):
                with self.subTest(device=device_name, field=field.name):
                    self.assertIsNone(field.verification_delay)

    def test_profiles_actually_have_select_fields(self):
        # Guards the rollout test against silently covering nothing.
        covered = {
            device_name
            for device_name, device_cls in DEVICES.items()
            if self._selects(device_cls)
        }
        self.assertGreaterEqual(len(covered), 15)


if __name__ == "__main__":
    unittest.main()

import unittest

from bluetti_bt_lib.devices import DEVICES
from bluetti_bt_lib.fields import SelectField

# Every device reflects a select write back slowly, so each SelectField has to
# declare the same verification delay the slow number controls use.
SELECT_VERIFICATION_DELAY = 2.0


class TestSelectDelayRollout(unittest.TestCase):
    def _selects(self, device_cls):
        return [f for f in device_cls().fields if isinstance(f, SelectField)]

    def test_every_select_declares_the_verification_delay(self):
        for device_name, device_cls in DEVICES.items():
            for field in self._selects(device_cls):
                with self.subTest(device=device_name, field=field.name):
                    self.assertEqual(
                        field.verification_delay, SELECT_VERIFICATION_DELAY
                    )

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

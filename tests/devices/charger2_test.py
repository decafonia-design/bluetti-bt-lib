import unittest

from bluetti_bt_lib.devices.charger2 import (
    CHARGER2,
    Charger2SilentChargingField,
    Charger2SystemSwitchField,
)
from bluetti_bt_lib.fields import FieldName


class TestCharger2(unittest.TestCase):
    def setUp(self):
        self.system_field = Charger2SystemSwitchField(
            FieldName.CTRL_SYSTEM_ON_OFF,
            15600,
        )
        self.silent_field = Charger2SilentChargingField(
            FieldName.CTRL_SILENT_CHARGING,
            15600,
        )
        self.device = CHARGER2()

    def test_all_four_register_states(self):
        expected = {
            "5529": (True, False),
            "AA2A": (False, False),
            "AA26": (False, True),
            "5525": (True, True),
        }

        for hex_value, (system_on, silent_charging) in expected.items():
            with self.subTest(register_value=hex_value):
                data = bytes.fromhex(hex_value)
                self.assertEqual(self.system_field.parse(data), system_on)
                self.assertEqual(
                    self.silent_field.parse(data),
                    silent_charging,
                )

    def test_both_fields_reject_unknown_register_value(self):
        data = bytes.fromhex("1234")

        with self.assertRaises(ValueError):
            self.system_field.parse(data)

        with self.assertRaises(ValueError):
            self.silent_field.parse(data)

    def test_both_controls_are_classified_as_switches(self):
        switch_fields = [
            field.name for field in self.device.get_switch_fields()
        ]

        self.assertIn(FieldName.CTRL_SYSTEM_ON_OFF.value, switch_fields)
        self.assertIn(FieldName.CTRL_SILENT_CHARGING.value, switch_fields)

    def test_both_controls_are_not_classified_as_sensors(self):
        sensor_fields = [
            field.name for field in self.device.get_sensor_fields()
        ]

        self.assertNotIn(FieldName.CTRL_SYSTEM_ON_OFF.value, sensor_fields)
        self.assertNotIn(FieldName.CTRL_SILENT_CHARGING.value, sensor_fields)

    def test_both_controls_require_read_modify_write(self):
        for field_name in (
            FieldName.CTRL_SYSTEM_ON_OFF.value,
            FieldName.CTRL_SILENT_CHARGING.value,
        ):
            with self.subTest(field=field_name):
                with self.assertRaises(ValueError):
                    self.device.build_write_command(field_name, True)


if __name__ == "__main__":
    unittest.main()

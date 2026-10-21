from enum import Enum
import struct
import unittest
from bluetti_bt_lib.base_devices import BluettiDevice
from bluetti_bt_lib.fields import (
    BoolField,
    BoolFieldNonZero,
    DecimalField,
    EnumField,
    SelectField,
    StringField,
    SerialNumberField,
    UIntField,
    FieldName,
    SwitchField,
)
from bluetti_bt_lib.registers import ReadableRegisters


class Dummy(Enum):
    VALUE_0 = 0
    VALUE_1 = 1
    VALUE_2 = 2


class TestBluettiDevice(unittest.TestCase):
    def test_get_registers_empty(self):
        device = BluettiDevice(fields=[], pack_fields=[], max_packs=0)

        registers = device.get_polling_registers()
        self.assertEqual(registers, [])

        pack_registers = device.get_pack_polling_registers()
        self.assertEqual(pack_registers, [])

    def test_get_empty_fields(self):
        device = BluettiDevice(fields=[], pack_fields=[], max_packs=0)

        self.assertEqual(device.get_bool_fields(), [])
        self.assertEqual(device.get_switch_fields(), [])
        self.assertEqual(device.get_select_fields(), [])
        self.assertEqual(device.get_sensor_fields(), [])

    def test_not_implemented_methods(self):
        device = BluettiDevice(fields=[], pack_fields=[], max_packs=0)

        with self.assertRaises(NotImplementedError):
            device.get_full_registers_range()

        with self.assertRaises(NotImplementedError):
            device.get_device_type_registers()

        with self.assertRaises(NotImplementedError):
            device.get_device_sn_registers()

        with self.assertRaises(NotImplementedError):
            device.get_iot_version()

        with self.assertRaises(NotImplementedError):
            device.get_pack_selector(1)

    def test_parse(self):
        fields = [
            StringField(FieldName.DEVICE_TYPE, 200, 6),
            SerialNumberField(FieldName.DEVICE_SN, 100),
            BoolField(FieldName.CTRL_AC, 150),
        ]

        device = BluettiDevice(fields)

        raw: bytes = b"\x00\x00\x00\x01\x00\x00"

        parsed = device.parse(starting_address=149, data=raw)

        self.assertEqual(len(parsed), 1)
        self.assertTrue(parsed.get(FieldName.CTRL_AC.value))

    def test_parse_invalid(self):
        fields = [
            StringField(FieldName.DEVICE_TYPE, 200, 6),
            SerialNumberField(FieldName.DEVICE_SN, 100),
            BoolField(FieldName.CTRL_AC, 150),
        ]

        device = BluettiDevice(fields)

        raw: bytes = b"\x00\x00\x00\x02\x00\x00"

        parsed = device.parse(starting_address=149, data=raw)

        self.assertEqual(len(parsed), 1)
        self.assertIsNone(parsed.get(FieldName.CTRL_AC.value))

    def test_build_write_command(self):
        fields = [
            SwitchField(FieldName.CTRL_AC, 150),
        ]

        device = BluettiDevice(fields)

        command = device.build_write_command(FieldName.CTRL_AC.value, True)

        self.assertEqual(command.address, 150)
        self.assertEqual(command.value, 1)

    def test_build_write_command_not_writeable(self):
        fields = [
            BoolField(FieldName.CTRL_DC, 160),
        ]

        device = BluettiDevice(fields)

        command = device.build_write_command(FieldName.CTRL_DC.value, False)

        self.assertIsNone(command)

    def test_initialization_with_fields(self):
        fields = [
            StringField(FieldName.DEVICE_TYPE, 200, 6),
            SerialNumberField(FieldName.DEVICE_SN, 100),
            BoolField(FieldName.CTRL_AC, 150),
            BoolFieldNonZero(FieldName.AC_OUTPUT_ON, 2011),
        ]
        pack_fields = [
            StringField(FieldName.PACK_TYPE, 300, 6),
        ]

        device = BluettiDevice(fields=fields, pack_fields=pack_fields, max_packs=2)

        polling_registers = device.get_polling_registers()
        self.assertEqual(len(polling_registers), 4)
        self.assertIsInstance(polling_registers[0], ReadableRegisters)
        self.assertIsInstance(polling_registers[1], ReadableRegisters)
        self.assertIsInstance(polling_registers[2], ReadableRegisters)

        # Check if sorted correctly by address
        self.assertEqual(polling_registers[0].starting_address, 100)
        self.assertEqual(polling_registers[1].starting_address, 150)
        self.assertEqual(polling_registers[2].starting_address, 200)
        self.assertEqual(polling_registers[3].starting_address, 2011)

        pack_polling_registers = device.get_pack_polling_registers()
        self.assertEqual(len(pack_polling_registers), 1)
        self.assertIsInstance(pack_polling_registers[0], ReadableRegisters)
        self.assertEqual(pack_polling_registers[0].starting_address, 300)

        sensor_fields = device.get_sensor_fields()
        self.assertEqual(len(sensor_fields), 2)

        bool_fields = device.get_bool_fields()
        self.assertEqual(len(bool_fields), 2)

    def test_coalesces_nearby_fields_into_one_block(self):
        # Reading one field per request costs a round trip each. Fields that
        # sit within the gap limit are covered by a single read instead.
        fields = [
            UIntField(FieldName.AC_OUTPUT_POWER, 38),
            UIntField(FieldName.DC_OUTPUT_POWER, 39),
            UIntField(FieldName.BATTERY_SOC, 43, min=0, max=100),
        ]

        device = BluettiDevice(fields=fields)

        blocks = device.get_polling_registers()
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].starting_address, 38)
        self.assertEqual(blocks[0].quantity, 6)

        # Every field is inside a block that gets read, and the reply is
        # sliced by offset, so the values still land on the right field.
        raw = struct.pack("!HHHHHH", 500, 300, 0, 0, 0, 80)
        parsed = device.parse(starting_address=38, data=raw)
        self.assertEqual(parsed[FieldName.AC_OUTPUT_POWER.value], 500)
        self.assertEqual(parsed[FieldName.DC_OUTPUT_POWER.value], 300)
        self.assertEqual(parsed[FieldName.BATTERY_SOC.value], 80)

    def test_distant_fields_stay_separate(self):
        fields = [
            UIntField(FieldName.AC_OUTPUT_POWER, 38),
            UIntField(FieldName.DC_OUTPUT_POWER, 39),
            UIntField(FieldName.BATTERY_SOC, 70, min=0, max=100),
        ]

        device = BluettiDevice(fields=fields)

        blocks = device.get_polling_registers()
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].quantity, 2)
        self.assertEqual(blocks[1].starting_address, 70)

    def test_block_never_grows_past_the_limit(self):
        fields = [
            UIntField(FieldName.AC_OUTPUT_POWER, 38),
            UIntField(FieldName.DC_OUTPUT_POWER, 39),
            UIntField(FieldName.BATTERY_SOC, 48, min=0, max=100),
        ]

        device = BluettiDevice(fields=fields)

        blocks = device.get_polling_registers()
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].quantity, 2)
        self.assertEqual(blocks[1].starting_address, 48)

    def test_oversized_field_keeps_its_own_block(self):
        # A field wider than the block limit cannot fit inside it, and the
        # limit stops anything else from joining it.
        fields = [
            StringField(FieldName.DEVICE_TYPE, 100, 12),
            BoolField(FieldName.CTRL_AC, 113),
        ]

        device = BluettiDevice(fields=fields)

        blocks = device.get_polling_registers()
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].starting_address, 100)
        self.assertEqual(blocks[0].quantity, 12)
        self.assertEqual(blocks[1].starting_address, 113)

    def test_pack_fields_keep_one_request_each(self):
        pack_fields = [
            DecimalField(FieldName.PACK_VOLTAGE, 98, 2),
            UIntField(FieldName.PACK_BATTERY_SOC, 99),
        ]

        device = BluettiDevice(
            fields=[], pack_fields=pack_fields, max_packs=4
        )

        blocks = device.get_pack_polling_registers()
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].starting_address, 98)
        self.assertEqual(blocks[0].quantity, 1)
        self.assertEqual(blocks[1].starting_address, 99)
        self.assertEqual(blocks[1].quantity, 1)

    def test_switch_fields(self):
        fields = [
            SwitchField(FieldName.CTRL_AC, 150),
            BoolField(FieldName.CTRL_DC, 160),
        ]

        device = BluettiDevice(fields=fields, pack_fields=[], max_packs=0)

        self.assertEqual(len(device.get_switch_fields()), 1)
        self.assertEqual(len(device.get_bool_fields()), 1)

    def test_select_fields(self):
        fields = [
            SelectField(FieldName.CTRL_CHARGING_MODE, 180, Dummy),
            EnumField(FieldName.AC_OUTPUT_MODE, 70, Dummy),
        ]

        device = BluettiDevice(fields=fields, pack_fields=[], max_packs=0)

        self.assertEqual(len(device.get_select_fields()), 1)
        self.assertEqual(len(device.get_sensor_fields()), 1)

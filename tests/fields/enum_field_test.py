from enum import Enum
import unittest
from bluetti_bt_lib.fields import EnumField, FieldName


class Dummy(Enum):
    VALUE_0 = 0
    VALUE_1 = 1
    VALUE_2 = 2


class TestEnumField(unittest.TestCase):
    def test_parse(self):
        field = EnumField(FieldName.AC_OUTPUT_MODE, 70, Dummy)

        result = field.parse(b"\x00\x00")
        self.assertEqual(result, Dummy.VALUE_0)

        result = field.parse(b"\x00\x01")
        self.assertEqual(result, Dummy.VALUE_1)

        result = field.parse(b"\x00\x02")
        self.assertEqual(result, Dummy.VALUE_2)

        result = field.parse(b"\x00\x03")
        self.assertIsNone(result)

    def test_is_writeable(self):
        self.field = EnumField(FieldName.AC_OUTPUT_MODE, 70, Dummy)
        self.assertFalse(self.field.is_writeable())

    def test_to_option(self):
        field = EnumField(FieldName.AC_OUTPUT_MODE, 70, Dummy)

        # The three ways a caller refers to an option all name the same one.
        self.assertIs(field.to_option("VALUE_1"), Dummy.VALUE_1)
        self.assertIs(field.to_option(Dummy.VALUE_1), Dummy.VALUE_1)
        self.assertIs(field.to_option(1), Dummy.VALUE_1)

        # Nothing this field can hold, so the caller keeps what it was given.
        self.assertIsNone(field.to_option("NOPE"))
        self.assertIsNone(field.to_option(7))
        self.assertIsNone(field.to_option(None))


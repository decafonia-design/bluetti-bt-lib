import asyncio
from decimal import Decimal
import unittest

from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption
from bluetti_bt_lib.devices import AC180P
from bluetti_bt_lib import DeviceReader, FieldName


class TestAC180P(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._createMock()

    def _createMock(self):
        # Raw values read from a real AC180P (IoT protocol 2004)
        self.ble_mock = ClientMockNoEncryption()

        self.ble_mock.add_r_int(102, 51)
        self.ble_mock.add_r_sstr(110, "AC180P", 6)
        self.ble_mock.add_r_sn(116, 2335000530383)

        self.ble_mock.add_r_int(140, 0)
        self.ble_mock.add_r_int(142, 0)
        self.ble_mock.add_r_int(144, 53)
        self.ble_mock.add_r_int(146, 0)

        self.ble_mock.add_r_int(1213, 0x0175)
        self.ble_mock.add_r_int(1214, 0x000E)
        self.ble_mock.add_r_int(1314, 0x000B)
        self.ble_mock.add_r_int(1500, 0x01F3)
        self.ble_mock.add_r_int(1511, 0x08FA)

        self.ble_mock.add_r_int(2011, 1)
        self.ble_mock.add_r_int(2012, 0)
        self.ble_mock.add_r_int(2020, 0)
        self.ble_mock.add_r_int(2021, 1)
        self.ble_mock.add_r_int(2022, 30)
        self.ble_mock.add_r_int(2023, 90)

    async def _read(self):
        reader = DeviceReader(
            "00:11:00:11:00:11",
            AC180P(),
            asyncio.Future,
            ble_client=self.ble_mock,
        )

        return await reader.read()

    async def test_ac180p(self):
        data = await self._read()

        self.assertIsNotNone(data)

        self.assertEqual(data.get(FieldName.DEVICE_TYPE.value), "AC180P")
        self.assertEqual(data.get(FieldName.BATTERY_SOC.value), 51)

        self.assertEqual(data.get(FieldName.DC_OUTPUT_POWER.value), 0)
        self.assertEqual(data.get(FieldName.AC_OUTPUT_POWER.value), 0)
        self.assertEqual(data.get(FieldName.DC_INPUT_POWER.value), 53)
        self.assertEqual(data.get(FieldName.AC_INPUT_POWER.value), 0)

        self.assertEqual(data.get(FieldName.DC_INPUT_VOLTAGE.value), Decimal("37.3"))
        self.assertEqual(data.get(FieldName.DC_INPUT_CURRENT.value), Decimal("1.4"))
        self.assertEqual(data.get(FieldName.AC_INPUT_VOLTAGE.value), Decimal("1.1"))
        self.assertEqual(data.get(FieldName.AC_OUTPUT_FREQUENCY.value), Decimal("49.9"))
        self.assertEqual(data.get(FieldName.AC_OUTPUT_VOLTAGE.value), Decimal("229.8"))

        self.assertEqual(data.get(FieldName.BATTERY_SOC_RANGE_START.value), 30)
        self.assertEqual(data.get(FieldName.BATTERY_SOC_RANGE_END.value), 90)

    async def test_unset_soc_range_is_left_out(self):
        # A unit that never had charge limits set in the app answers 0 here,
        # which is below the 5% the app accepts, so it is not a reading.
        self.ble_mock.add_r_int(2022, 0)
        self.ble_mock.add_r_int(2023, 0)

        data = await self._read()

        self.assertIsNotNone(data)
        self.assertNotIn(FieldName.BATTERY_SOC_RANGE_START.value, data)
        self.assertNotIn(FieldName.BATTERY_SOC_RANGE_END.value, data)


if __name__ == "__main__":
    unittest.main()

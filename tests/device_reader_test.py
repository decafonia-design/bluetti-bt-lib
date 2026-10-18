import asyncio
import unittest

from bleak.exc import BleakError

from bluetti_bt_lib.base_devices import BaseDeviceV1
from bluetti_bt_lib import DeviceReader
from bluetti_bt_lib.bluetooth import DeviceReaderConfig
from bluetti_bt_lib.fields import FieldName
from bluetti_bt_lib.registers import ReadableRegisters
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption


class TestDeviceReader(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ble_mock = ClientMockNoEncryption()

        # Device type
        self.ble_mock.add_r_str(10, "AC300", 6)
        # Serial
        self.ble_mock.add_r_sn(17, 2300000000000)
        # DC input power
        self.ble_mock.add_r_int(36, 10)
        # AC input power
        self.ble_mock.add_r_int(37, 8)
        # AC output power
        self.ble_mock.add_r_int(38, 9)
        # AC output power
        self.ble_mock.add_r_int(39, 7)
        # SOC
        self.ble_mock.add_r_int(43, 78)

    async def test_read_all_correct(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        data = await reader.read()

        self.assertEqual(data.get(FieldName.DEVICE_TYPE.value), "AC300")
        self.assertEqual(data.get(FieldName.DEVICE_SN.value), 2300000000000)
        self.assertEqual(data.get(FieldName.DC_INPUT_POWER.value), 10)
        self.assertEqual(data.get(FieldName.AC_INPUT_POWER.value), 8)
        self.assertEqual(data.get(FieldName.AC_OUTPUT_POWER.value), 9)
        self.assertEqual(data.get(FieldName.DC_OUTPUT_POWER.value), 7)
        self.assertEqual(data.get(FieldName.BATTERY_SOC.value), 78)

    async def test_read_soc_wrong(self):
        # SOC
        self.ble_mock.add_r_int(43, 1234)

        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        data = await reader.read()

        self.assertIsNone(data.get(FieldName.BATTERY_SOC.value))

    async def test_failed_notify_setup_is_cleaned_up(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        original_start_notify = self.ble_mock.start_notify

        async def start_notify_then_fail(char_specifier, callback, **kwargs):
            await original_start_notify(char_specifier, callback, **kwargs)
            raise RuntimeError("Simulated notification setup failure")

        self.ble_mock.start_notify = start_notify_then_fail

        self.assertFalse(await reader.connect())
        self.assertIsNotNone(self.ble_mock._callback)

        await reader.disconnect()

        self.assertIsNone(self.ble_mock._callback)
        self.assertTrue(self.ble_mock.is_connected)

    async def test_connection_drop_clears_per_connection_state(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        self.assertTrue(await reader.connect())
        self.assertTrue(reader.has_notifier)

        original_write = self.ble_mock.write_gatt_char

        async def write_drops_connection(*args, **kwargs):
            raise BleakError("connection dropped")

        self.ble_mock.write_gatt_char = write_drops_connection

        data = await reader.read([ReadableRegisters(36, 1)])

        self.ble_mock.write_gatt_char = original_write

        self.assertIsNone(data)
        self.assertFalse(reader._connected)
        # The notifier flag must be cleared so the next connect()
        # re-subscribes on the replacement client instead of silently
        # waiting for notifications that never arrive.
        self.assertFalse(reader.has_notifier)

    async def test_reconnect_after_drop_resubscribes_notify(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        self.assertTrue(await reader.connect())

        original_write = self.ble_mock.write_gatt_char

        async def write_drops_connection(*args, **kwargs):
            raise BleakError("connection dropped")

        self.ble_mock.write_gatt_char = write_drops_connection
        self.assertIsNone(await reader.read([ReadableRegisters(36, 1)]))

        # Simulate recovery: once the connection works again the reader
        # must re-subscribe the notifier and read normally.
        self.ble_mock.write_gatt_char = original_write

        data = await reader.read([ReadableRegisters(36, 1)])
        self.assertEqual(data.get(FieldName.DC_INPUT_POWER.value), 10)

    async def test_failed_notify_setup_is_retried_on_next_connect(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        original_start_notify = self.ble_mock.start_notify

        async def start_notify_fails(char_specifier, callback, **kwargs):
            raise RuntimeError("Simulated subscription failure")

        self.ble_mock.start_notify = start_notify_fails
        self.assertFalse(await reader.connect())

        # The failed subscription must not be remembered as active:
        # the next connect() has to retry start_notify() and then read.
        self.ble_mock.start_notify = original_start_notify

        self.assertTrue(await reader.connect())
        self.assertIsNotNone(self.ble_mock._callback)

        data = await reader.read([ReadableRegisters(36, 1)])
        self.assertEqual(data.get(FieldName.DC_INPUT_POWER.value), 10)

    async def test_connect_cancellation_propagates(self):
        device = BaseDeviceV1()
        reader = DeviceReader(
            "00:11:00:11:00:11",
            device,
            asyncio.Future,
            DeviceReaderConfig(timeout=15, use_encryption=True),
            ble_client=self.ble_mock,
            lock=asyncio.Lock(),
        )

        # The encrypted handshake never completes with this mock, so the
        # task sits in the handshake wait loop until it is cancelled.
        task = asyncio.create_task(reader.connect())
        await asyncio.sleep(0.1)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertFalse(reader._connected)

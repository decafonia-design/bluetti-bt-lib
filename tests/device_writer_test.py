import asyncio
import time
import unittest

from bleak.exc import BleakError

from bluetti_bt_lib.bluetooth import DeviceWriter, DeviceWriterConfig
from bluetti_bt_lib.bluetooth.device_writer import _select_verification_delay
from bluetti_bt_lib.bluetooth.encryption import BluettiEncryption
from bluetti_bt_lib.devices.ac180 import AC180
from bluetti_bt_lib.fields import FieldName, NumberField, UIntField
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption

NOTIFY_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


class TestDeviceWriter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ble_mock = ClientMockNoEncryption()
        self.device = AC180()

    def build_writer(self, use_encryption: bool = False) -> DeviceWriter:
        return DeviceWriter(
            self.ble_mock,
            self.device,
            DeviceWriterConfig(timeout=15, use_encryption=use_encryption),
            asyncio.Lock(),
        )

    async def test_write_without_notifier_does_not_wait_for_ack(self):
        writer = self.build_writer()

        start = time.monotonic()
        result = await writer.write(FieldName.CTRL_AC.value, True)
        elapsed = time.monotonic() - start

        self.assertTrue(result)
        # No notifier means no acknowledgement, so the write must not block
        self.assertLess(elapsed, 1)
        self.assertTrue(self.ble_mock.is_connected)

    async def test_attach_shares_connection_without_second_notifier(self):
        async def on_notify(*_):
            return None

        notify_calls = 0
        original_start_notify = self.ble_mock.start_notify

        async def counting_start_notify(*args, **kwargs):
            nonlocal notify_calls
            notify_calls += 1
            await original_start_notify(*args, **kwargs)

        self.ble_mock.start_notify = counting_start_notify

        # A reader owns the notifier of the shared connection
        await self.ble_mock.start_notify(NOTIFY_UUID, on_notify)
        self.assertEqual(notify_calls, 1)

        writer = self.build_writer()
        writer.attach()

        start = time.monotonic()
        result = await writer.write(FieldName.CTRL_AC.value, True)
        elapsed = time.monotonic() - start

        self.assertTrue(result)
        self.assertLess(elapsed, 1)
        # The writer must not register a notifier of its own
        self.assertEqual(notify_calls, 1)

    async def test_disconnect_keeps_borrowed_session(self):
        encryption = BluettiEncryption()
        encryption.secure_aes_key = b"0" * 16

        writer = self.build_writer()
        writer.attach(encryption=encryption)

        await writer.disconnect()

        self.assertIs(writer.encryption, encryption)
        self.assertEqual(encryption.secure_aes_key, b"0" * 16)

    async def test_disconnect_attached_keeps_shared_client_connected(self):
        writer = self.build_writer()
        writer.attach()

        await writer.disconnect()

        # The client belongs to the reader's shared connection; the
        # writer must not pull it down and leave the reader stranded.
        self.assertTrue(self.ble_mock.is_connected)
        self.assertFalse(writer._connected)

    async def test_disconnect_resets_own_session(self):
        writer = self.build_writer()
        await writer.connect()
        writer.encryption.secure_aes_key = b"0" * 16

        await writer.disconnect()

        self.assertIsNone(writer.encryption.secure_aes_key)
        self.assertFalse(self.ble_mock.is_connected)

    async def test_standalone_reconnect_resubscribes_notifier(self):
        notify_calls = 0
        original_start_notify = self.ble_mock.start_notify

        async def counting_start_notify(*args, **kwargs):
            nonlocal notify_calls
            notify_calls += 1
            await original_start_notify(*args, **kwargs)

        self.ble_mock.start_notify = counting_start_notify

        # The mock never completes the key exchange, so each connect()
        # attempt fails at the handshake wait. Every attempt must still
        # (re-)subscribe the notifier instead of trusting stale
        # ownership state left over from the previous connection.
        writer = DeviceWriter(
            self.ble_mock,
            self.device,
            DeviceWriterConfig(timeout=1, use_encryption=True),
            asyncio.Lock(),
        )

        self.assertFalse(await writer.connect())
        self.assertFalse(writer._owns_notifier)
        self.assertFalse(await writer.connect())

        self.assertEqual(notify_calls, 2)

    def test_verification_delay_selection(self):
        fast = UIntField(FieldName.DC_INPUT_POWER, 36)
        # Default short delay, extended for Charger 2 shared controls.
        self.assertEqual(_select_verification_delay(fast, False), 0.7)
        self.assertEqual(_select_verification_delay(fast, True), 2.0)

        # A field-declared delay wins over both defaults.
        slow = NumberField(
            FieldName.BATTERY_SOC_RANGE_START,
            3015,
            1,
            0,
            100,
            5,
            verification_delay=3.0,
        )
        self.assertEqual(_select_verification_delay(slow, False), 3.0)
        self.assertEqual(_select_verification_delay(slow, True), 3.0)

    async def test_write_bleak_error_clears_notifier_ownership(self):
        writer = DeviceWriter(
            self.ble_mock,
            self.device,
            DeviceWriterConfig(timeout=5, use_encryption=True),
            asyncio.Lock(),
        )

        original_start_notify = self.ble_mock.start_notify

        async def start_notify_completes_handshake(char, callback, **kwargs):
            await original_start_notify(char, callback, **kwargs)
            # Pretend the key exchange completed so connect() proceeds.
            writer.encryption.secure_aes_key = b"0" * 16
            writer.encryption_ready.set()

        self.ble_mock.start_notify = start_notify_completes_handshake

        self.assertTrue(await writer.connect())
        self.assertTrue(writer._owns_notifier)

        async def write_drops_connection(*args, **kwargs):
            raise BleakError("connection dropped")

        self.ble_mock.write_gatt_char = write_drops_connection

        result = await writer.write(FieldName.CTRL_AC.value, True)

        self.assertFalse(result)
        self.assertFalse(writer._connected)
        # Ownership must be forgotten so the next connect() re-subscribes
        # the notifier for the new connection lifecycle.
        self.assertFalse(writer._owns_notifier)
        self.assertFalse(writer.has_notifier)

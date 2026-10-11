import asyncio
import struct
import unittest

from bluetti_bt_lib.bluetooth import DeviceWriter, DeviceWriterConfig
from bluetti_bt_lib.bluetooth.device_reader import DeviceReader, DeviceReaderConfig
from bluetti_bt_lib.devices.charger2 import CHARGER2, CHARGER2_CONTROL_STATES
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption


class TestCharger2Writer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = ClientMockNoEncryption()
        self.device = CHARGER2()
        self.lock = asyncio.Lock()

        self.reader = DeviceReader(
            mac=self.client.address,
            bluetti_device=self.device,
            future_builder_method=asyncio.get_running_loop().create_future,
            config=DeviceReaderConfig(timeout=10),
            lock=self.lock,
            ble_client=self.client,
        )

        self.writer = DeviceWriter(
            self.client,
            self.device,
            DeviceWriterConfig(timeout=10),
            self.lock,
            reader=self.reader,
        )

        self.writes = []
        original_write = self.client.write_gatt_char

        async def capture_write(char_specifier, data, response=None):
            command = bytes(data)
            if len(command) >= 2 and command[1] == 6:
                self.writes.append(command)
                return
            await original_write(char_specifier, data, response)

        self.client.write_gatt_char = capture_write

    async def asyncTearDown(self):
        await self.reader.disconnect()

    async def test_controls_preserve_other_control_for_all_valid_states(self):
        controls = {
            "ctrl_system_on_off": 0,
            "ctrl_silent_charging": 1,
        }

        for initial_word, initial_state in CHARGER2_CONTROL_STATES.items():
            for field, state_index in controls.items():
                for desired_value in (False, True):
                    with self.subTest(
                        initial_word=f"0x{initial_word:04X}",
                        field=field,
                        desired_value=desired_value,
                    ):
                        self.client.add_r_int(15600, initial_word)
                        self.writes.clear()

                        result = await self.writer.write(field, desired_value)

                        self.assertTrue(result)
                        self.assertEqual(len(self.writes), 1)

                        command = struct.unpack("!HHHH", self.writes[0][:8])
                        self.assertEqual(command[0], 0x0106)  # Device ID + function code
                        self.assertEqual(command[1], 15600)   # Register address

                        expected_state = list(initial_state)
                        expected_state[state_index] = desired_value
                        expected_word = next(
                            word
                            for word, state in CHARGER2_CONTROL_STATES.items()
                            if state == tuple(expected_state)
                        )

                        self.assertEqual(command[2], expected_word)  # Register value

    async def test_unknown_register_value_is_rejected_without_writing(self):
        self.client.add_r_int(15600, 0x1234)

        result = await self.writer.write("ctrl_system_on_off", True)

        self.assertFalse(result)
        self.assertEqual(self.writes, [])

    async def test_control_write_requires_reader(self):
        writer = DeviceWriter(
            self.client,
            self.device,
            DeviceWriterConfig(timeout=10),
            asyncio.Lock(),
        )

        result = await writer.write("ctrl_system_on_off", True)

        self.assertFalse(result)
        self.assertEqual(self.writes, [])

    async def test_non_boolean_control_value_is_rejected(self):
        result = await self.writer.write("ctrl_system_on_off", 1)

        self.assertFalse(result)
        self.assertEqual(self.writes, [])


if __name__ == "__main__":
    unittest.main()

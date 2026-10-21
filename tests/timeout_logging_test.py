import asyncio
import logging
import unittest
from unittest.mock import patch

from bluetti_bt_lib import DeviceReader
from bluetti_bt_lib.base_devices import BaseDeviceV1
from bluetti_bt_lib.bluetooth import device_reader
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption

# A request is given RESPONSE_TIMEOUT_SECONDS to be answered; a test should not
# spend five seconds waiting for one that is never coming.
FAST_TIMEOUT_SECONDS = 0.05


class DeafMock(ClientMockNoEncryption):
    """Answers every request except the ones numbered in deaf_at."""

    def __init__(self, deaf_at: set[int]) -> None:
        super().__init__()
        self.deaf_at = deaf_at
        self.requests = 0

    async def write_gatt_char(self, char_specifier, data, response=None) -> None:
        self.requests += 1
        if self.requests in self.deaf_at:
            return

        await super().write_gatt_char(char_specifier, data, response)


class TestTimeoutLogging(unittest.IsolatedAsyncioTestCase):
    def make_reader(self, ble_mock: ClientMockNoEncryption) -> DeviceReader:
        return DeviceReader(
            "00:11:00:11:00:11",
            BaseDeviceV1(),
            asyncio.Future,
            ble_client=ble_mock,
            lock=asyncio.Lock(),
        )

    def levels(self, logs, text: str) -> list[int]:
        """Levels of the records mentioning text."""
        return [r.levelno for r in logs.records if text in r.getMessage()]

    async def test_a_link_that_has_not_answered_yet_logs_quietly(self):
        # A station that is still waking misses the first request, which is
        # normal enough that it should not fill the HA log at startup.
        ble_mock = DeafMock({1})
        reader = self.make_reader(ble_mock)

        with patch.object(
            device_reader, "RESPONSE_TIMEOUT_SECONDS", FAST_TIMEOUT_SECONDS
        ):
            with self.assertLogs(reader.logger, level="DEBUG") as logs:
                data = await reader.read()

        self.assertIsNone(data)
        self.assertEqual(self.levels(logs, "No valid response"), [logging.DEBUG])
        self.assertEqual(self.levels(logs, "Read aborted"), [logging.DEBUG])

    async def test_a_link_that_stopped_answering_still_warns(self):
        # Once the station has proven it is answering, a missing answer is news.
        ble_mock = DeafMock({2})
        reader = self.make_reader(ble_mock)

        with patch.object(
            device_reader, "RESPONSE_TIMEOUT_SECONDS", FAST_TIMEOUT_SECONDS
        ):
            with self.assertLogs(reader.logger, level="DEBUG") as logs:
                data = await reader.read()

        self.assertIsNone(data)
        self.assertEqual(self.levels(logs, "No valid response"), [logging.WARNING])
        self.assertEqual(self.levels(logs, "Read aborted"), [logging.WARNING])


if __name__ == "__main__":
    unittest.main()

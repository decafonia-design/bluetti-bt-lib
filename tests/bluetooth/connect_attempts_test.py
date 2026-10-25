import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bluetti_bt_lib.bluetooth.device_reader import DeviceReader, DeviceReaderConfig
from bluetti_bt_lib.devices import EL300


class TestConnectAttempts(unittest.IsolatedAsyncioTestCase):
    def test_default_stays_ten(self):
        self.assertEqual(DeviceReaderConfig().max_attempts, 10)

    async def test_connect_passes_the_configured_attempts(self):
        device = MagicMock()
        device.name = "EL30012345678"
        with patch(
            "bluetti_bt_lib.bluetooth.device_reader.BleakScanner.find_device_by_address",
            AsyncMock(return_value=device),
        ), patch(
            "bluetti_bt_lib.bluetooth.device_reader.establish_connection",
            AsyncMock(side_effect=RuntimeError("stop here")),
        ) as establish:
            reader = DeviceReader(
                "AA:BB:CC:DD:EE:FF",
                EL300(),
                asyncio.Future,
                DeviceReaderConfig(max_attempts=3),
            )
            try:
                await reader.connect()
            except RuntimeError:
                pass
        self.assertEqual(establish.call_args.kwargs["max_attempts"], 3)

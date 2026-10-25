import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bluetti_bt_lib.bluetooth.device_reader import (
    DeviceReader,
    DeviceReaderConfig,
    bluez_adapter_kwargs,
)
from bluetti_bt_lib.devices import EL300
from bluetti_bt_lib.scripts import bluetti_read, bluetti_write


class TestAdapter(unittest.IsolatedAsyncioTestCase):
    def test_default_is_the_system_adapter(self):
        self.assertIsNone(DeviceReaderConfig().adapter)
        self.assertEqual(bluez_adapter_kwargs(None), {})
        self.assertEqual(bluez_adapter_kwargs(""), {})
        self.assertEqual(bluez_adapter_kwargs("hci1"), {"bluez": {"adapter": "hci1"}})

    async def _connect(self, config):
        device = MagicMock()
        device.name = "EL30012345678"
        with patch(
            "bluetti_bt_lib.bluetooth.device_reader.BleakScanner.find_device_by_address",
            AsyncMock(return_value=device),
        ) as find, patch(
            "bluetti_bt_lib.bluetooth.device_reader.establish_connection",
            AsyncMock(side_effect=RuntimeError("stop here")),
        ) as establish:
            reader = DeviceReader(
                "AA:BB:CC:DD:EE:FF", EL300(), asyncio.Future, config
            )
            try:
                await reader.connect()
            except RuntimeError:
                pass
        return find, establish

    async def test_scan_and_connect_use_the_configured_adapter(self):
        find, establish = await self._connect(DeviceReaderConfig(adapter="hci1"))
        self.assertEqual(find.call_args.kwargs["bluez"], {"adapter": "hci1"})
        self.assertEqual(establish.call_args.kwargs["bluez"], {"adapter": "hci1"})

    async def test_without_adapter_bleak_picks_the_default(self):
        find, establish = await self._connect(DeviceReaderConfig())
        self.assertNotIn("bluez", find.call_args.kwargs)
        self.assertNotIn("bluez", establish.call_args.kwargs)

    async def test_write_script_connects_through_the_adapter(self):
        writer = MagicMock()
        writer.write = AsyncMock(return_value=True)
        with patch.object(bluetti_write, "BleakClient") as client, patch.object(
            bluetti_write, "DeviceWriter", return_value=writer
        ):
            await bluetti_write.async_write(
                "AA:BB:CC:DD:EE:FF", "EL300", True, "ctrl_ac", True, "hci1"
            )
        client.assert_called_once_with("AA:BB:CC:DD:EE:FF", bluez={"adapter": "hci1"})
        writer.write.assert_awaited_once_with("ctrl_ac", True)

    async def test_write_script_default_adapter(self):
        writer = MagicMock()
        writer.write = AsyncMock(return_value=True)
        with patch.object(bluetti_write, "BleakClient") as client, patch.object(
            bluetti_write, "DeviceWriter", return_value=writer
        ):
            await bluetti_write.async_write(
                "AA:BB:CC:DD:EE:FF", "EL300", True, "ctrl_ac", True
            )
        client.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    async def test_read_script_passes_the_adapter(self):
        reader = MagicMock()
        reader.read = AsyncMock(return_value=None)
        with patch.object(bluetti_read, "DeviceReader", return_value=reader) as built:
            await bluetti_read.async_read_device(
                "AA:BB:CC:DD:EE:FF", "EL300", True, "hci1"
            )
        self.assertEqual(built.call_args.args[3].adapter, "hci1")

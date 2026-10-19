import asyncio
import unittest

from bluetti_bt_lib import DeviceReader
from bluetti_bt_lib.devices import AC200M, AC300, AC500
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption

# The V1 tower stations all report their installed pack count at register 96
# and keep the per-pack data behind the pack selector at 3006.
PACK_STATIONS = (AC200M, AC300, AC500)


def _reader(device):
    return DeviceReader("00:11:00:11:00:11", device, asyncio.Future)


class TestPackCount(unittest.TestCase):
    def test_pack_stations_read_pack_num_at_96(self):
        for device_cls in PACK_STATIONS:
            with self.subTest(device=device_cls.__name__):
                device = device_cls()
                field = next(f for f in device.fields if f.name == "pack_num")
                self.assertEqual(field.address, 96)
                self.assertEqual([f.name for f in device.pack_fields], ["battery_soc"])
                self.assertGreater(device.max_packs, 0)

    def test_max_packs_is_a_ceiling_not_the_polled_count(self):
        # Slots each station physically holds, used only to bound a bad or
        # missing reading.
        self.assertEqual(AC200M().max_packs, 3)
        self.assertEqual(AC300().max_packs, 4)
        self.assertEqual(AC500().max_packs, 6)

    def test_installed_count_is_used(self):
        self.assertEqual(_reader(AC500())._pack_poll_count({"pack_num": 2}), 2)

    def test_no_packs_skips_the_pack_poll(self):
        self.assertEqual(_reader(AC500())._pack_poll_count({"pack_num": 0}), 0)

    def test_missing_reading_falls_back_to_the_ceiling(self):
        # Profiles without a pack_num field, or a read that excluded it.
        self.assertEqual(_reader(AC500())._pack_poll_count({}), 6)
        self.assertEqual(_reader(AC500())._pack_poll_count({"pack_num": None}), 6)

    def test_reported_count_is_clamped_to_the_ceiling(self):
        self.assertEqual(_reader(AC300())._pack_poll_count({"pack_num": 9}), 4)
        self.assertEqual(_reader(AC200M())._pack_poll_count({"pack_num": 99}), 3)


class TestPackPolling(unittest.IsolatedAsyncioTestCase):
    async def test_only_installed_packs_are_polled(self):
        ble_mock = ClientMockNoEncryption()
        ble_mock.add_r_str(10, "AC500", 6)
        ble_mock.add_r_sn(17, 2551110023321)
        ble_mock.add_r_int(43, 80)
        ble_mock.add_r_int(96, 2)
        ble_mock.add_r_int(99, 77)

        reader = DeviceReader(
            "00:11:00:11:00:11",
            AC500(),
            asyncio.Future,
            ble_client=ble_mock,
        )

        data = await reader.read()

        self.assertIsNotNone(data)
        self.assertEqual(data.get("pack_num"), 2)
        self.assertEqual(data.get("pack_1_battery_soc"), 77)
        self.assertEqual(data.get("pack_2_battery_soc"), 77)
        # Slots 3 to 6 are empty, so they are never selected or parsed.
        self.assertNotIn("pack_3_battery_soc", data)
        self.assertNotIn("pack_6_battery_soc", data)


if __name__ == "__main__":
    unittest.main()

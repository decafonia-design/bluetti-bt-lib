"""A MODBUS function 03 answer does not say which registers it carries, so the
reader has to reject answers that cannot belong to the request it is waiting for:
a late answer to an earlier request, a write acknowledgement, or a corrupted frame."""

import asyncio
import struct
import unittest
from unittest.mock import patch

from crcmod.predefined import mkCrcFun


from bluetti_bt_lib import DeviceReader
from bluetti_bt_lib.bluetooth import device_reader
from bluetti_bt_lib.devices import AC60
from bluetti_bt_lib.registers import ReadableRegisters, WriteableRegister
from bluetti_bt_lib.utils.bleak_client_mock import ClientMockNoEncryption

PACK_NUM_REGISTER = 96
modbus_crc = mkCrcFun("modbus")


def frame(slave: int, body: bytes) -> bytearray:
    """A function 03 answer carrying body."""
    return ClientMockNoEncryption()._read_frame(slave, body)


def exception_frame(register) -> bytearray:
    """A MODBUS exception answer to register: slave, function + 0x80, code, CRC."""
    response = bytearray([register.cmd[0], register.register_action.value + 0x80, 2])
    response += struct.pack("<H", modbus_crc(bytes(response)))
    return response


class ScriptedMock(ClientMockNoEncryption):
    """Answers the next command with queued notifications, then behaves normally.

    ``deaf`` stations answer nothing at all, however many times they are asked.
    """

    def __init__(self, deaf: bool = False) -> None:
        super().__init__()
        self.replies: list[bytes] = []
        self.commands: list[bytes] = []
        self.unsubscribed = 0
        self.deaf = deaf

    async def write_gatt_char(self, char, data, response=None) -> None:
        request = bytes(data)
        self.commands.append(request)
        if self.deaf:
            return
        replies, self.replies = self.replies, []
        if replies:
            for chunk in replies:
                await self._callback(char, bytearray(chunk))
            return
        await super().write_gatt_char(char, request, response)

    async def stop_notify(self, char) -> None:
        self.unsubscribed += 1
        self._callback = None


class TestRegisterValidation(unittest.TestCase):
    def test_read_answer_must_match_this_request(self):
        registers = ReadableRegisters(PACK_NUM_REGISTER, 1)
        self.assertTrue(registers.is_valid_response(frame(1, b"\x00\x04")))

        # An answer to a wider read: same function, different byte count.
        self.assertFalse(registers.is_valid_response(frame(1, b"\x00\x04\x00\x03")))
        # A write acknowledgement is not an answer to a read.
        self.assertFalse(WriteableRegister(PACK_NUM_REGISTER, 1).is_valid_response(frame(1, b"\x00\x04")))
        # Corrupted payload.
        broken = bytearray(frame(1, b"\x00\x04"))
        broken[3] ^= 0xFF
        self.assertFalse(registers.is_valid_response(bytes(broken)))

    def test_write_answer_must_echo_the_request(self):
        command = WriteableRegister(PACK_NUM_REGISTER, 1)
        self.assertTrue(command.is_valid_response(bytes(command.cmd)))
        self.assertFalse(
            command.is_valid_response(bytes(WriteableRegister(PACK_NUM_REGISTER, 0)))
        )

    def test_exception_answer_is_recognised(self):
        registers = ReadableRegisters(PACK_NUM_REGISTER, 1)
        response = exception_frame(registers)
        self.assertTrue(registers.is_valid_exception(bytes(response)))
        self.assertFalse(registers.is_valid_response(bytes(response)))


class LateMock(ClientMockNoEncryption):
    """Answers every request after a delay, like a busy station.

    ``first`` is the delay of the first answers, then ``latency``. Answers are
    not lost, only late: a request that times out and is asked again ends up
    answered twice.
    """

    def __init__(self, latency: float, first: list[float] | None = None) -> None:
        super().__init__()
        self.latency = latency
        self.first = list(first or [])
        self.commands: list[bytes] = []
        self.tasks: list[asyncio.Task] = []

    async def write_gatt_char(self, char, data, response=None) -> None:
        request = bytes(data)
        self.commands.append(request)
        answers = []
        callback = self._callback

        async def collect(c, content):
            answers.append(bytes(content))

        self._callback = collect
        await super().write_gatt_char(char, request, response)
        self._callback = callback

        delay = self.first.pop(0) if self.first else self.latency

        async def later():
            await asyncio.sleep(delay)
            for answer in answers:
                if self._callback is not None:
                    await self._callback(char, bytearray(answer))

        self.tasks.append(asyncio.create_task(later()))


class TestSecondAnswerToARetry(unittest.IsolatedAsyncioTestCase):
    async def test_second_answer_is_not_taken_by_the_next_request(self):
        # The reader waits 0.3 s. The first answer takes 0.45 s, so the read is
        # asked again; that second ask is answered too (0.25 s later), while
        # the next request of the same size is already waiting. That answer
        # must not end up as the value of the next register.
        ble_mock = LateMock(latency=0.25, first=[0.45])
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        ble_mock.add_r_int(PACK_NUM_REGISTER + 1, 7)
        reader = DeviceReader(
            "00:11:00:11:00:11",
            AC60(),
            asyncio.get_running_loop().create_future,
            ble_client=ble_mock,
        )

        with patch.object(device_reader, "RESPONSE_TIMEOUT_SECONDS", 0.3), patch.object(
            device_reader, "RETRY_PAUSE_SECONDS", 0
        ), patch.object(device_reader, "STRAY_ANSWER_SECONDS", 1):
            first = await reader.read_locked(
                [ReadableRegisters(PACK_NUM_REGISTER, 1)], raw=True
            )
            second = await reader.read_locked(
                [ReadableRegisters(PACK_NUM_REGISTER + 1, 1)], raw=True
            )

        self.assertEqual(first, {PACK_NUM_REGISTER: b"\x00\x04"})
        self.assertEqual(second, {PACK_NUM_REGISTER + 1: b"\x00\x07"})
        await asyncio.gather(*ble_mock.tasks)

    async def test_no_wait_when_the_first_ask_was_answered(self):
        ble_mock = LateMock(latency=0)
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        reader = DeviceReader(
            "00:11:00:11:00:11",
            AC60(),
            asyncio.get_running_loop().create_future,
            ble_client=ble_mock,
        )
        drained = []

        async def drain(registers):
            drained.append(registers)
        reader._drain_stray_answer = drain

        values = await reader.read_locked(
            [ReadableRegisters(PACK_NUM_REGISTER, 1)], raw=True
        )

        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})
        self.assertEqual(drained, [])
        await asyncio.gather(*ble_mock.tasks)


class TestReaderValidation(unittest.IsolatedAsyncioTestCase):
    async def _read_pack_num(self, ble_mock, registers=None):
        reader = DeviceReader(
            "00:11:00:11:00:11",
            AC60(),
            asyncio.get_running_loop().create_future,
            ble_client=ble_mock,
        )
        return reader, await reader.read_locked(
            registers or [ReadableRegisters(PACK_NUM_REGISTER, 1)], raw=True
        )

    async def test_answer_for_another_request_is_discarded(self):
        ble_mock = ScriptedMock()
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        # A late answer to a 3-word read, then the real answer.
        ble_mock.replies = [
            bytes(frame(1, b"\x00\x04\x00\x03\x00\x02")),
            bytes(frame(1, b"\x00\x04")),
        ]

        _, values = await self._read_pack_num(ble_mock)
        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})

    async def test_corrupted_answer_is_discarded(self):
        ble_mock = ScriptedMock()
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        broken = bytearray(frame(1, b"\x00\x04"))
        broken[4] ^= 0xFF
        ble_mock.replies = [bytes(broken), bytes(frame(1, b"\x00\x04"))]

        _, values = await self._read_pack_num(ble_mock)
        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})

    async def test_answer_split_over_notifications_is_reassembled(self):
        ble_mock = ScriptedMock()
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        answer = bytes(frame(1, b"\x00\x04"))
        ble_mock.replies = [answer[:4], answer[4:]]

        _, values = await self._read_pack_num(ble_mock)
        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})

    async def test_write_ack_is_not_taken_for_a_read(self):
        ble_mock = ScriptedMock()
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)
        command = WriteableRegister(PACK_NUM_REGISTER, 1)
        ble_mock.replies = [bytes(command.cmd), bytes(frame(1, b"\x00\x04"))]

        _, values = await self._read_pack_num(ble_mock)
        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})

    async def test_exception_answer_leaves_the_field_out(self):
        ble_mock = ScriptedMock()
        registers = [ReadableRegisters(PACK_NUM_REGISTER, 1)]
        ble_mock.replies = [bytes(exception_frame(registers[0]))]

        _, values = await self._read_pack_num(ble_mock, registers)
        self.assertEqual(values, {PACK_NUM_REGISTER: b""})

    async def test_no_answer_aborts_the_read_and_resyncs(self):
        ble_mock = ScriptedMock(deaf=True)
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)

        with patch.object(device_reader, "RESPONSE_TIMEOUT_SECONDS", 0.2):
            reader, values = await self._read_pack_num(ble_mock)

        self.assertIsNone(values)
        # Giving up takes two asks, and both of them are the same request.
        self.assertEqual(len(ble_mock.commands), 2)
        self.assertEqual(ble_mock.unsubscribed, 1)
        self.assertIsNone(reader.notify_future)

    async def test_resynced_link_is_subscribed_again(self):
        ble_mock = ScriptedMock(deaf=True)
        ble_mock.add_r_int(PACK_NUM_REGISTER, 4)

        with patch.object(device_reader, "RESPONSE_TIMEOUT_SECONDS", 0.2):
            reader, values = await self._read_pack_num(ble_mock)
            self.assertIsNone(values)

            ble_mock.deaf = False
            values = await reader.read_locked(
                [ReadableRegisters(PACK_NUM_REGISTER, 1)], raw=True
            )

        self.assertEqual(values, {PACK_NUM_REGISTER: b"\x00\x04"})
        self.assertEqual(ble_mock.unsubscribed, 1)


if __name__ == "__main__":
    unittest.main()

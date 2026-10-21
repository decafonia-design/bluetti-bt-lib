"""Probe how a station reports its pack count before and after a pack walk.

Register 96 (PACK_NUM) counts installed packs, and BaseDeviceV1 selects a pack
slot by writing the slot number to register 3006. Other implementations (for
example bluetti_mqtt) read 3006 as "pack_num", so the same register may both
select a slot and report the count. If that is the case, walking the slots
would leave the last probed slot number in 3006 and could change what the
station reports as its pack count afterwards.

Each round reads 96 and 3001-3008 raw, walks the slots, then reads them again,
and prints the three independent signals side by side:

  reg96      what register 96 says
  reg3006    what register 3006 says
  slots      which slots actually answered the walk

Run with the pipx venv python:
  ~/.local/share/pipx/venvs/bluetti-bt-lib-sidieje/bin/python pack-count-probe.py -m <MAC> -t AC300
Add --enc for the encrypted stations (Elite V2 models, AP300, EL10, Charger 2).
Use --no-walk to read the registers without touching 3006 at all.
Use --reset N to write N into the selector after the walk and read the
registers again: it shows whether the count follows a later write, or whether
the station only remembers the highest slot it was ever given.

Each round also prints the selector writes the reader actually sent, so a run
says whether the walk restored the selector rather than assuming it did.
"""

import argparse
import asyncio

import bluetti_bt_lib
from bluetti_bt_lib.bluetooth.device_reader import DeviceReader, DeviceReaderConfig
from bluetti_bt_lib.fields import FieldName
from bluetti_bt_lib.registers import ReadableRegisters, WriteableRegister
from bluetti_bt_lib.utils.device_builder import build_device

PACK_COUNT_REGISTER = 96
SELECTOR_REGISTER = 3006
# Read the block the profile already polls (3001-3008 on AC300/AC500) so the
# answer is one the station is used to giving, rather than a lone 3006 read it
# may refuse.
BLOCK_START = 3001
BLOCK_QUANTITY = 8


def decode(body: bytes) -> list[int]:
    """Split a MODBUS read body into big-endian uint16 values."""
    return [
        int.from_bytes(body[index : index + 2], "big")
        for index in range(0, len(body) - 1, 2)
    ]


async def read_raw(reader: DeviceReader, label: str) -> dict[int, int]:
    """Read register 96 and the selector block without parsing any fields."""
    data = await reader.read(
        only_registers=[
            ReadableRegisters(PACK_COUNT_REGISTER, 1),
            ReadableRegisters(BLOCK_START, BLOCK_QUANTITY),
        ],
        raw=True,
    )
    if data is None:
        print(f"    {label}: read failed")
        return {}

    count_body = data.get(PACK_COUNT_REGISTER, b"")
    block_body = data.get(BLOCK_START, b"")
    values = decode(block_body)

    print(
        f"    {label}: reg{PACK_COUNT_REGISTER}="
        f"{decode(count_body)[0] if count_body else '?'}"
        f"  reg{SELECTOR_REGISTER}="
        f"{values[SELECTOR_REGISTER - BLOCK_START] if values else '?'}"
        f"  block{BLOCK_START}={values}"
    )
    return {PACK_COUNT_REGISTER: decode(count_body)[0] if count_body else None}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mac", required=True)
    parser.add_argument("-t", "--type", required=True)
    parser.add_argument("--enc", action="store_true", help="station needs encryption")
    parser.add_argument("-n", "--rounds", type=int, default=3)
    parser.add_argument("--gap", type=float, default=5.0)
    parser.add_argument(
        "--no-walk",
        action="store_true",
        help="only read the registers; never write the pack selector",
    )
    parser.add_argument(
        "--reset",
        type=int,
        metavar="N",
        help="after the walk, write N to the selector and read the registers again",
    )
    args = parser.parse_args()

    device = build_device(args.type + "12345678")
    if device is None:
        print("unsupported type")
        return

    reader = DeviceReader(
        args.mac,
        device,
        asyncio.Future,
        DeviceReaderConfig(use_encryption=args.enc),
    )

    print(
        f"{args.type}: max_packs={device.max_packs}, "
        f"selector writes {[pack for pack in range(1, device.max_packs + 1)]}"
    )
    # Which copy of the library is under test, so a run can be read as evidence
    # about a particular build.
    print(f"library: {bluetti_bt_lib.__file__}")

    # Record every write to the selector register, whoever sends it. This is how
    # a run shows whether the reader put the selector back after walking.
    selector_writes: list[int] = []
    send_command = reader._async_send_command

    async def recording_send(registers):
        if (
            isinstance(registers, WriteableRegister)
            and registers.address == SELECTOR_REGISTER
        ):
            selector_writes.append(registers.value)
        return await send_command(registers)

    reader._async_send_command = recording_send

    for round_number in range(1, args.rounds + 1):
        print(f"[{round_number}]")

        before = await read_raw(reader, "before walk")

        slots: list[int] = []
        if not args.no_walk:
            data = await reader.read(include_packs=True)
            if data is None:
                print("    walk: read failed")
                # A failed read leaves the link up with the notifier cleared;
                # drop it or the station stops advertising and every later
                # round fails with "Device not found".
                await reader.disconnect()
            else:
                slots = data.get(FieldName.PACK_SLOTS.value) or []
                reported = data.get(FieldName.PACK_NUM.value)
                print(f"    walk: reg96 as parsed={reported}  slots={slots}")

            print(f"    selector writes: {selector_writes}")
            selector_writes.clear()

            after = await read_raw(reader, "after walk")

            if before and after:
                first, second = (
                    before[PACK_COUNT_REGISTER],
                    after[PACK_COUNT_REGISTER],
                )
                if first != second:
                    print(
                        f"    >>> register {PACK_COUNT_REGISTER} moved "
                        f"{first} -> {second} across the walk"
                    )

            if args.reset is not None:
                # Does the count follow a later write, or only the highest slot
                # ever written? If it follows, an inflated count can be put
                # right afterwards. If it does not, the walk has to be bounded
                # instead of repaired.
                await reader._async_send_command(
                    WriteableRegister(SELECTOR_REGISTER, args.reset)
                )
                await asyncio.sleep(1)
                await read_raw(
                    reader, f"after writing {args.reset} to {SELECTOR_REGISTER}"
                )
                print(f"    selector writes: {selector_writes}")
                selector_writes.clear()
        else:
            await read_raw(reader, "no walk")

        await asyncio.sleep(args.gap)


asyncio.run(main())

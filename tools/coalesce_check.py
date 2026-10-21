"""Compare poll time and field coverage across repeated reads.

Run with the pipx venv python:
  ~/.local/share/pipx/venvs/bluetti-bt-lib-sidieje/bin/python ~/coalesce-check.py -m <MAC> -t AC300
Add --enc for the encrypted stations (Elite V2 models, AP300, EL10, Charger 2).
"""

import argparse
import asyncio
import statistics
import time

from bluetti_bt_lib.bluetooth.device_reader import DeviceReader, DeviceReaderConfig
from bluetti_bt_lib.fields import FieldName
from bluetti_bt_lib.utils.device_builder import build_device


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mac", required=True)
    parser.add_argument("-t", "--type", required=True)
    parser.add_argument("--enc", action="store_true", help="station needs encryption")
    parser.add_argument("-n", "--rounds", type=int, default=5)
    parser.add_argument(
        "--gap", type=float, default=2.0, help="seconds between rounds"
    )
    parser.add_argument(
        "--packs-every",
        type=int,
        default=1,
        help="walk the pack slots every Nth round (0 = never, 1 = every round)",
    )
    args = parser.parse_args()

    device = build_device(args.type + "12345678")
    if device is None:
        print("unsupported type")
        return

    # Pack fields answer per slot as pack_<slot>_<name>, so the bare names are
    # not expected keys; the slots that answered come back in pack_slots.
    expected = {field.name for field in device.fields}
    pack_names = [field.name for field in device.pack_fields]
    uses_packs = bool(pack_names) and device.max_packs > 0
    if uses_packs:
        expected.add(FieldName.PACK_SLOTS.value)

    print(f"{args.type}: {len(device.polling_registers)} main blocks, "
          f"{len(device.pack_polling_registers)} pack blocks, "
          f"{device.max_packs} pack slots, {len(expected)} expected fields")

    reader = DeviceReader(
        args.mac,
        device,
        asyncio.Future,
        DeviceReaderConfig(use_encryption=args.enc),
    )

    times: list[float] = []
    fast_times: list[float] = []
    ok = 0
    missing_all: set[str] = set()
    main_only = expected - {FieldName.PACK_SLOTS.value}

    for round_number in range(1, args.rounds + 1):
        walk_packs = args.packs_every >= 1 and (
            args.packs_every == 1 or round_number % args.packs_every == 0
        )
        started = time.monotonic()
        data = await reader.read(include_packs=walk_packs)
        elapsed = time.monotonic() - started
        times.append(elapsed)
        if not walk_packs:
            fast_times.append(elapsed)

        if data is None:
            print(f"[{round_number}] {elapsed:5.1f}s  FAILED")
            # A failed read leaves the link up with the notifier cleared.
            # Standalone runs have to drop it themselves, otherwise the
            # station is still connected to us, stops advertising, and every
            # later round fails with "Device not found". Home Assistant does
            # not hit this because it hands the reader a client it owns.
            await reader.disconnect()
        else:
            ok += 1
            check = expected if walk_packs else main_only
            missing = {name for name in check if name not in data}
            if walk_packs and uses_packs:
                for slot in data.get(FieldName.PACK_SLOTS.value) or []:
                    for name in pack_names:
                        if f"pack_{slot}_{name}" not in data:
                            missing.add(f"pack_{slot}_{name}")
            missing_all |= missing
            pack_values = ", ".join(
                f"s{slot}:{data.get(f'pack_{slot}_voltage')}V"
                for slot in data.get(FieldName.PACK_SLOTS.value) or []
            )
            print(
                f"[{round_number}] {elapsed:5.1f}s  {len(data)} fields"
                + ("" if walk_packs else "  no pack walk")
                + (f"  packs[{pack_values}]" if uses_packs and pack_values else "")
                + (f"  missing: {sorted(missing)}" if missing else "")
            )

        await asyncio.sleep(args.gap)

    print(f"\n{ok}/{args.rounds} rounds answered, median {statistics.median(times):.1f}s")
    if fast_times:
        print(f"no-pack rounds: median {statistics.median(fast_times):.1f}s")
    if missing_all:
        print("fields never answered:", sorted(missing_all))
    else:
        print("every expected field answered")


asyncio.run(main())

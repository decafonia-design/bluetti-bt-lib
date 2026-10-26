import struct

from ..base_devices import BaseDeviceV2
from ..bluetooth import ReadableRegisters
from ..enums import ChargingPriority, ReverseChargingMode
from ..fields import (
    SelectField,
    SwitchField,
    FieldName,
    UIntField,
    DecimalField,
    SwapStringField,
    SerialNumberField,
    SignedDecimalField,
)
from ..registers import WriteableRegister


# Register 15600 contains both the system state and silent charging state.
# Each entry is: (system_on, silent_charging).
CHARGER2_CONTROL_STATES = {
    0x5529: (True, False),
    0xAA2A: (False, False),
    0xAA26: (False, True),
    0x5525: (True, True),
}


class Charger2ControlField(SwitchField):
    """Decode one boolean control from Charger 2 register 15600."""

    def __init__(self, name: FieldName, address: int, state_index: int):
        super().__init__(name, address)
        self.state_index = state_index

    def parse(self, data: bytes) -> bool:
        value = struct.unpack("!H", data)[0]

        try:
            state = CHARGER2_CONTROL_STATES[value]
        except KeyError:
            raise ValueError(
                f"Unexpected Charger 2 control value: 0x{value:04X}"
            ) from None

        return state[self.state_index]

    def is_writeable(self) -> bool:
        return True

    def allowed_write_type(self, value) -> bool:
        return isinstance(value, bool)


class Charger2SystemSwitchField(Charger2ControlField):
    """Charger 2 system on/off control."""

    def __init__(self, name: FieldName, address: int):
        super().__init__(name, address, state_index=0)


class Charger2SilentChargingField(Charger2ControlField):
    """Charger 2 silent charging control."""

    def __init__(self, name: FieldName, address: int):
        super().__init__(name, address, state_index=1)


# Register 15626 holds the reverse charging (starter battery) settings.
# Low two bits: 0b01 = on, 0b10 = off, the same pairs as in 15600.
# High byte: the selected mode, kept while reverse charging is off.
# Seen on a Charger 2: 0x0169 trickle on, 0x0269 pulse on, 0x0469 top-up on,
# 0x046A top-up selected but off, 0x016A trickle selected but off.
REVERSE_CHARGING_ON = 0b01
REVERSE_CHARGING_OFF = 0b10


def _reverse_charging_state(value: int) -> int | None:
    """The on/off bits of 15626, or None if the word is not a known layout.

    The high byte must hold a known mode as well: a late answer from another
    register (0x5529 from 15600 was seen in a test read) would otherwise look
    like "on".
    """
    modes = {mode.value for mode in ReverseChargingMode}
    state = value & 0b11
    if value >> 8 not in modes or state not in (
        REVERSE_CHARGING_ON,
        REVERSE_CHARGING_OFF,
    ):
        return None
    return state


class Charger2ReverseChargingField(SwitchField):
    """Reverse charging on/off, the low two bits of register 15626.

    Written as a read-modify-write (see compose), so the selected mode and
    the other bits of the register are kept.
    """

    def parse(self, data: bytes) -> bool:
        value = struct.unpack("!H", data)[0]
        state = _reverse_charging_state(value)

        if state == REVERSE_CHARGING_ON:
            return True
        if state == REVERSE_CHARGING_OFF:
            return False
        raise ValueError(
            f"Unexpected Charger 2 reverse charging value: 0x{value:04X}"
        )

    def allowed_write_type(self, value) -> bool:
        return isinstance(value, bool)

    def compose(self, current: int, value) -> int | None:
        """Register value that sets this switch and keeps everything else."""
        if not isinstance(value, bool):
            return None
        if _reverse_charging_state(current) is None:
            return None
        state = REVERSE_CHARGING_ON if value else REVERSE_CHARGING_OFF
        return (current & ~0b11 & 0xFFFF) | state


class Charger2ReverseChargingModeField(SelectField):
    """Reverse charging mode, the high byte of register 15626."""

    def __init__(self, name: FieldName, address: int):
        super().__init__(name, address, ReverseChargingMode)

    def parse(self, data: bytes) -> ReverseChargingMode:
        value = struct.unpack("!H", data)[0]

        try:
            return ReverseChargingMode(value >> 8)
        except ValueError:
            raise ValueError(
                f"Unexpected Charger 2 reverse charging mode: 0x{value:04X}"
            ) from None

    def compose(self, current: int, value) -> int | None:
        """Register value that selects this mode and keeps the low byte."""
        option = self.to_option(value)
        if option is None or _reverse_charging_state(current) is None:
            return None
        return (option.value << 8) | (current & 0x00FF)


# Register 15625 holds "Priority Charging" (Advanced Settings in the app) in
# bits 4-5, with the same pairs as 15600: 0b01 BLUETTI Products, 0b10 Portable
# Power Station. Seen on a Charger 2: 0x0016 and 0x0026. The other bits stayed
# 0x06 and are not known, so only that layout is accepted; anything else (a
# late answer from another register, or a setting not seen yet) is skipped
# rather than guessed.
CHARGING_PRIORITY_MASK = 0x30
CHARGING_PRIORITY_REST = 0x06


def _charging_priority(value: int) -> ChargingPriority | None:
    if value & ~CHARGING_PRIORITY_MASK & 0xFFFF != CHARGING_PRIORITY_REST:
        return None
    try:
        return ChargingPriority((value & CHARGING_PRIORITY_MASK) >> 4)
    except ValueError:
        return None


class Charger2ChargingPriorityField(SelectField):
    """Priority Charging, bits 4-5 of register 15625."""

    def __init__(self, name: FieldName, address: int):
        super().__init__(name, address, ChargingPriority)

    def parse(self, data: bytes) -> ChargingPriority:
        value = struct.unpack("!H", data)[0]
        priority = _charging_priority(value)
        if priority is None:
            raise ValueError(
                f"Unexpected Charger 2 charging priority value: 0x{value:04X}"
            )
        return priority

    def compose(self, current: int, value) -> int | None:
        """Register value that selects this priority and keeps the other bits."""
        option = self.to_option(value)
        if option is None or _charging_priority(current) is None:
            return None
        return (current & ~CHARGING_PRIORITY_MASK & 0xFFFF) | (option.value << 4)


class CHARGER2(BaseDeviceV2):
    def __init__(self):
        super().__init__(
            [
                DecimalField(FieldName.DC_INPUT_VOLTAGE, 15531, 1),
                DecimalField(FieldName.DC_INPUT_CURRENT, 15532, 2),
                UIntField(FieldName.DC_INPUT_POWER, 15534),

                DecimalField(FieldName.DC_2_OUTPUT_VOLTAGE, 15535, 1),
                SignedDecimalField(
                    FieldName.DC_2_OUTPUT_CURRENT, 15536, 2, multiplier=-1
                ),
                SignedDecimalField(
                    FieldName.DC_2_OUTPUT_POWER_TOTAL, 15538, 0, multiplier=-1
                ),

                DecimalField(FieldName.B_VOLTAGE, 15543, 1),
                SignedDecimalField(
                    FieldName.B_IO_POWER, 15546, 0, multiplier=-1
                ),
                UIntField(FieldName.BATTERY_SOC, 15584),

                DecimalField(FieldName.B_ALT_VOLTAGE, 15539, 1),
                # Starter battery side: positive while the vehicle (alternator)
                # charges through the Charger 2, negative while reverse
                # charging feeds the starter battery.
                SignedDecimalField(FieldName.B_ALT_CURRENT, 15540, 2),
                SignedDecimalField(FieldName.B_ALT_IO_POWER, 15542, 0),

                Charger2SystemSwitchField(
                    FieldName.CTRL_SYSTEM_ON_OFF,
                    15600,
                ),
                Charger2SilentChargingField(
                    FieldName.CTRL_SILENT_CHARGING,
                    15600,
                ),
                Charger2ChargingPriorityField(
                    FieldName.CTRL_CHARGING_PRIORITY,
                    15625,
                ),
                Charger2ReverseChargingField(
                    FieldName.CTRL_REVERSE_CHARGING,
                    15626,
                ),
                Charger2ReverseChargingModeField(
                    FieldName.CTRL_REVERSE_CHARGING_MODE,
                    15626,
                ),
                # Reverse charging power in W as set in the app (100 W seen);
                # read only until a write has been confirmed on a device.
                UIntField(FieldName.REVERSE_CHARGING_POWER, 15631),

                SwapStringField(FieldName.DEVICE_TYPE, 15500, 6),
                SerialNumberField(FieldName.DEVICE_SN, 15506),
            ],
            include_common_fields=False,
        )

    def build_write_command(self, name: str, value):
        # These controls share register 15600, 15625 or 15626. Their writes must be
        # constructed by DeviceWriter using a fresh read-modify-write.
        # Do not construct a standalone command for any of them here.
        if name in (
            FieldName.CTRL_SYSTEM_ON_OFF.value,
            FieldName.CTRL_SILENT_CHARGING.value,
            FieldName.CTRL_REVERSE_CHARGING.value,
            FieldName.CTRL_REVERSE_CHARGING_MODE.value,
            FieldName.CTRL_CHARGING_PRIORITY.value,
        ):
            raise ValueError(
                "Charger 2 controls require a read-modify-write operation"
            )

        return super().build_write_command(name, value)

    def get_device_type_registers(self):
        return [
            ReadableRegisters(15500, 6),
        ]

    def get_device_sn_registers(self):
        return [
            ReadableRegisters(15506, 4),
        ]

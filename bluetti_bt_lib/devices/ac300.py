from ..base_devices import BaseDeviceV1
from ..fields import (
    FieldName,
    EnumField,
    DecimalField,
    UIntField,
    NumberField,
    SelectField,
    BoolField,
    SwitchField,
    VersionField,
)
from ..enums import OutputMode, UpsMode, SplitPhaseMode

# The tower's older Bluetooth stack is slower to reflect a control write in its
# own register than the newer stations are. Reading a switch back after the 1s
# default has been seen to return the value from before the write, which the
# write check then reports as a failure even though the switch did change.
SWITCH_VERIFICATION_DELAY = 1.5


class AC300(BaseDeviceV1):
    def __init__(self):
        super().__init__(
            [
                VersionField(FieldName.VER_ARM, 23),
                VersionField(FieldName.VER_DSP, 25),
                DecimalField(FieldName.POWER_GENERATION, 41, 1),
                EnumField(FieldName.AC_OUTPUT_MODE, 70, OutputMode),
                DecimalField(FieldName.INTERNAL_AC_VOLTAGE, 71, 1),
                DecimalField(FieldName.INTERNAL_AC_FREQUENCY, 74, 2),
                DecimalField(FieldName.AC_INPUT_VOLTAGE, 77, 1),
                DecimalField(FieldName.AC_INPUT_FREQUENCY, 80, 2),
                DecimalField(FieldName.PV_S1_VOLTAGE, 86, 1),
                DecimalField(FieldName.PV_S1_POWER, 87, 1, 10),
                DecimalField(FieldName.PV_S1_CURRENT, 88, 2, 10),
                # How many packs are installed. The reader polls it before the
                # pack walk and uses it to stop early, but it does not say
                # which slots are occupied, so it cannot pick them out.
                UIntField(FieldName.PACK_NUM, 96),
                SelectField(FieldName.CTRL_UPS_MODE, 3001, UpsMode),
                BoolField(FieldName.CTRL_SPLIT_PHASE, 3004),
                EnumField(FieldName.CTRL_SPLIT_PHASE_MODE, 3005, SplitPhaseMode),
                SwitchField(
                    FieldName.CTRL_AC, 3007, verification_delay=SWITCH_VERIFICATION_DELAY
                ),
                SwitchField(
                    FieldName.CTRL_DC, 3008, verification_delay=SWITCH_VERIFICATION_DELAY
                ),
                SwitchField(
                    FieldName.CTRL_GRID_CHARGE_ON,
                    3011,
                    verification_delay=SWITCH_VERIFICATION_DELAY,
                ),
                SwitchField(
                    FieldName.CTRL_TIME_CONTROL_ON,
                    3013,
                    verification_delay=SWITCH_VERIFICATION_DELAY,
                ),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_START,
                    3015,
                    1,
                    5,
                    100,
                    1,
                    verification_delay=2.0,
                ),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_END,
                    3016,
                    1,
                    5,
                    100,
                    1,
                    verification_delay=2.0,
                ),
                # SelectField(FieldName.CTRL_DISPLAY_TIMEOUT, 3061, DisplayMode),
            ],
            [
                # Per-pack readings, each selected by the write to 3006
                # (BaseDeviceV1.get_pack_selector). The read-only PACK_SELECTED
                # and the 16 per-pack cell voltages stay off the profile: the
                # selector write is independent of these fields, and sixteen
                # entities per pack is more noise than it is worth.
                DecimalField(FieldName.PACK_VOLTAGE, 98, 2),
                UIntField(FieldName.PACK_BATTERY_SOC, 99),
            ],
            # Every slot the tower can hold. The reader walks all of them and
            # drops the ones that answer with nothing, because register 96
            # counts packs without saying which slots they sit in.
            max_packs=4,
        )

from ..base_devices import BaseDeviceV1
from ..fields import (
    FieldName,
    EnumField,
    DecimalField,
    NumberField,
    SelectField,
    BoolField,
    SwitchField,
    UIntField,
)
from ..enums import OutputMode, DisplayMode, UpsMode, SplitPhaseMode


class AC500(BaseDeviceV1):
    def __init__(self):
        super().__init__(
            [
                EnumField(FieldName.AC_OUTPUT_MODE, 70, OutputMode),
                DecimalField(FieldName.INTERNAL_AC_VOLTAGE, 71, 1, 10),
                DecimalField(FieldName.INTERNAL_AC_FREQUENCY, 74, 2, 10),
                DecimalField(FieldName.AC_INPUT_VOLTAGE, 77, 1),
                DecimalField(FieldName.AC_INPUT_FREQUENCY, 80, 2),
                DecimalField(FieldName.PV_S1_VOLTAGE, 86, 1),
                DecimalField(FieldName.PV_S1_POWER, 87, 1, 10),
                DecimalField(FieldName.PV_S1_CURRENT, 88, 2, 10),
                # Packs actually installed. The reader polls this before the
                # pack loop, so only the installed packs are selected.
                UIntField(FieldName.PACK_NUM, 96),
                SelectField(FieldName.CTRL_UPS_MODE, 3001, UpsMode),
                BoolField(FieldName.CTRL_SPLIT_PHASE, 3004),
                EnumField(FieldName.CTRL_SPLIT_PHASE_MODE, 3005, SplitPhaseMode),
                SwitchField(FieldName.CTRL_AC, 3007),
                SwitchField(FieldName.CTRL_DC, 3008),
                SwitchField(FieldName.CTRL_GRID_CHARGE_ON, 3011),
                SwitchField(FieldName.CTRL_TIME_CONTROL_ON, 3013),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_START,
                    3015,
                    1,
                    0,
                    100,
                    5,
                    verification_delay=2.0,
                ),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_END,
                    3016,
                    1,
                    0,
                    100,
                    5,
                    verification_delay=2.0,
                ),
                SelectField(FieldName.CTRL_DISPLAY_TIMEOUT, 3061, DisplayMode),
            ],
            [
                # Same pack registers as the AC300: per-pack SOC at 99, with the
                # pack selected through the write to 3006.
                UIntField(FieldName.PACK_BATTERY_SOC, 99),
            ],
            # Ceiling, not the polled count: the reader stops at the pack count
            # register 96 reports. Two AC300 towers hold up to 6 packs.
            max_packs=6,
        )

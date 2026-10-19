from ..base_devices import BaseDeviceV1
from ..fields import (
    FieldName,
    EnumField,
    DecimalField,
    SwitchField,
    SelectField,
    UIntField,
)
from ..enums import OutputMode, DisplayMode


class AC200M(BaseDeviceV1):
    def __init__(self):
        super().__init__(
            [
                EnumField(FieldName.AC_OUTPUT_MODE, 70, OutputMode),
                DecimalField(FieldName.INTERNAL_AC_VOLTAGE, 71, 1, 10),
                DecimalField(FieldName.INTERNAL_AC_FREQUENCY, 74, 2, 10),
                DecimalField(FieldName.INTERNAL_DC_INPUT_VOLTAGE, 86, 1),
                DecimalField(FieldName.INTERNAL_DC_INPUT_POWER, 87, 1, 10),
                DecimalField(FieldName.INTERNAL_DC_INPUT_CURRENT, 88, 2),
                # Packs actually installed. The reader polls this before the
                # pack loop, so only the installed packs are selected.
                UIntField(FieldName.PACK_NUM, 96),
                SwitchField(FieldName.CTRL_AC, 3007),
                SwitchField(FieldName.CTRL_DC, 3008),
                SwitchField(FieldName.CTRL_POWER_OFF, 3060),
                SelectField(FieldName.CTRL_DISPLAY_TIMEOUT, 3061, DisplayMode),
            ],
            [
                # Same pack registers as the AC300: per-pack SOC at 99, with the
                # pack selected through the write to 3006.
                UIntField(FieldName.PACK_BATTERY_SOC, 99),
            ],
            # Ceiling, not the polled count: the reader stops at the pack count
            # register 96 reports. The AC200M holds an internal pack plus two
            # expansion packs.
            max_packs=3,
        )

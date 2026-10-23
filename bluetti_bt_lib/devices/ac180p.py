from ..base_devices import BaseDeviceV2
from ..enums import ChargingMode
from ..fields import (
    FieldName,
    UIntField,
    NumberField,
    SwitchField,
    SelectField,
    DecimalField,
)


class AC180P(BaseDeviceV2):
    def __init__(self):
        super().__init__(
            [
                UIntField(FieldName.DC_OUTPUT_POWER, 140),
                UIntField(FieldName.AC_OUTPUT_POWER, 142),
                UIntField(FieldName.DC_INPUT_POWER, 144),
                UIntField(FieldName.AC_INPUT_POWER, 146),
                DecimalField(FieldName.DC_INPUT_VOLTAGE, 1213, 1),
                DecimalField(FieldName.DC_INPUT_CURRENT, 1214, 1),
                DecimalField(FieldName.AC_INPUT_VOLTAGE, 1314, 1),
                DecimalField(FieldName.AC_OUTPUT_FREQUENCY, 1500, 1),
                DecimalField(FieldName.AC_OUTPUT_VOLTAGE, 1511, 1),
                SwitchField(FieldName.CTRL_AC, 2011),
                SwitchField(FieldName.CTRL_DC, 2012),
                SelectField(FieldName.CTRL_CHARGING_MODE, 2020, ChargingMode),
                SwitchField(FieldName.CTRL_POWER_LIFTING, 2021),
                # Same pair the other V2 stations use. A unit with no limits set
                # in the app reads 0 here, which the min of 5 drops.
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_START,
                    2022,
                    1,
                    5,
                    100,
                    1,
                    verification_delay=2.0,
                ),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_END,
                    2023,
                    1,
                    5,
                    100,
                    1,
                    verification_delay=2.0,
                ),
            ],
        )

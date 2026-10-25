from decimal import Decimal

from ..enums import BatteryStatus, EcoMode, DisplayMode, ChargingMode, WorkingModeEL300
from ..fields import (
    FieldName,
    UIntField,
    NumberField,
    SelectField,
    SwitchField,
    DecimalField,
    EnumField,
    OffsetIntField,
    SignedDecimalField,
    VersionField,
    SwapStringField,
)
from ..base_devices import BaseDeviceV2


class EL300(BaseDeviceV2):
    def __init__(self):
        super().__init__(
            [
                DecimalField(FieldName.TIME_REMAINING, 104, 0, 1 / Decimal(60)),
                # Verified on an owner's Elite 300 (dump of 25 Oct 2026, 96 %,
                # feeding ~7 W): 100 = 996 (99.6 V; ~30 LiFePO4 cells at 3.32 V),
                # 101 = 7 (0.07 A, so ~7 W, which matches the slow drop of the
                # charge level), 103 = 0 at that small load, 105 = 104 while
                # discharging. The scale of 101 differs from what other projects
                # give for the Elite 200 V2, so these stay on the Elite 300 only.
                DecimalField(FieldName.BATTERY_VOLTAGE, 100, 1, 1, Decimal(0), Decimal(200)),
                SignedDecimalField(FieldName.BATTERY_CURRENT, 101, 2, 1, Decimal(-100), Decimal(100)),
                EnumField(FieldName.BATTERY_STATUS, 103, BatteryStatus),
                DecimalField(FieldName.TIME_TO_EMPTY, 105, 0, 1 / Decimal(60)),
                # Lifetime energy in 0.1 kWh (same dump: 4, 65, 74, 56). They are
                # the low words of 32-bit counters; the high words (151, 153, ...)
                # read 0, so reading one register stays right up to 6553.5 kWh.
                DecimalField(FieldName.DC_OUTPUT_ENERGY, 150, 1),
                DecimalField(FieldName.AC_OUTPUT_ENERGY, 152, 1),
                DecimalField(FieldName.DC_INPUT_ENERGY, 154, 1),
                DecimalField(FieldName.AC_INPUT_ENERGY, 156, 1),
                UIntField(FieldName.DC_OUTPUT_POWER, 140),
                UIntField(FieldName.AC_OUTPUT_POWER, 142),
                UIntField(FieldName.DC_INPUT_POWER, 144),
                UIntField(FieldName.AC_INPUT_POWER, 146),
                DecimalField(FieldName.AC_INPUT_VOLTAGE, 1314, 1),
                DecimalField(FieldName.AC_INPUT_CURRENT, 1315, 1),
                # 1511 mirrors the grid input on this family, the real AC
                # output is 1431.
                DecimalField(FieldName.AC_OUTPUT_VOLTAGE, 1431, 1),
                # UPS working mode: V2 portables keep it at 2005 and use
                # different values than the V1 UpsMode register (3001). The
                # Elite 300 numbers them differently again (Customized UPS
                # reads 3), see WorkingModeEL300.
                SelectField(FieldName.CTRL_UPS_MODE, 2005, WorkingModeEL300),
                # UPS grid-charge enable; the AC300 exposes the same function
                # as ctrl_grid_charge_on (register 3011 there).
                SwitchField(FieldName.CTRL_GRID_CHARGE_ON, 2008),
                SwitchField(FieldName.CTRL_AC, 2011),
                SwitchField(FieldName.CTRL_DC, 2012),
                SwitchField(FieldName.CTRL_ECO_DC, 2014),
                SelectField(FieldName.CTRL_ECO_TIME_MODE_DC, 2015, EcoMode),
                # Owners report the same eco ranges as the EL100 V2: 5-20 W DC.
                NumberField(FieldName.CTRL_ECO_MIN_POWER_DC, 2016, 1, 5, 20, 1),
                SwitchField(FieldName.CTRL_ECO_AC, 2017),
                SelectField(FieldName.CTRL_ECO_TIME_MODE_AC, 2018, EcoMode),
                # ... and 10-40 W AC.
                NumberField(FieldName.CTRL_ECO_MIN_POWER_AC, 2019, 1, 10, 40, 1),
                SelectField(FieldName.CTRL_CHARGING_MODE, 2020, ChargingMode),
                SwitchField(FieldName.CTRL_POWER_LIFTING, 2021),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_START,
                    2022,
                    1,
                    5,
                    100,
                    1,
                ),
                NumberField(
                    FieldName.BATTERY_SOC_RANGE_END,
                    2023,
                    1,
                    5,
                    100,
                    1,
                ),
                SelectField(FieldName.CTRL_DISPLAY_TIMEOUT, 2067, DisplayMode),
                # Battery health and temperature (same dump): 6006 = 100 %,
                # 6007 = 54, stored as degrees Celsius + 40, so 14 degrees on a
                # cool October evening. The per-cell list from 6300 is not there
                # on the Elite 300 (only three values, and no answer from 6310).
                UIntField(FieldName.BATTERY_SOH, 6006, min=0, max=100),
                OffsetIntField(FieldName.BATTERY_TEMPERATURE, 6007, 40, min=-40, max=100),
                VersionField(FieldName.VER_BMS, 6175),
                SwapStringField(FieldName.WIFI_NAME, 12002, 16),
            ],
        )

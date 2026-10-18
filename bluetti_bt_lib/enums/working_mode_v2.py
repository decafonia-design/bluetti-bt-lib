from enum import Enum, unique


@unique
class WorkingModeV2(Enum):
    """Working mode (register 2005) on V2 portable units such as the Elite 100 V2.

    Values as used by the BLUETTI app and the official integration for V2;
    they differ from the V1 UpsMode (3001).
    """

    CUSTOMIZED = 1
    PV_PRIORITY = 2
    STANDARD = 4
    TIME_CONTROL = 5

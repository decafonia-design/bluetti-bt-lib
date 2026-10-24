from enum import Enum, unique


@unique
class WorkingModeEL300(Enum):
    """Working mode (register 2005) on the Elite 300.

    The Elite 300 numbers its modes differently from the other V2 portables
    (WorkingModeV2): an owner's unit in Customized UPS mode, as shown by the
    BLUETTI app and the official integration, reads 3 here, a value that
    WorkingModeV2 does not know. The other three modes (PV Priority, Standard,
    Time Control) have not been seen on this model yet, so they stay unmapped
    rather than guessed.
    """

    CUSTOMIZED = 3

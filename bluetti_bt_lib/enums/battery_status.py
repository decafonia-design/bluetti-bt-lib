from enum import Enum, unique


@unique
class BatteryStatus(Enum):
    """Charge direction of the battery (register 103) on the V2 portables.

    An owner's Elite 300 reads 0 while it only feeds a few watts, so a small
    load does not count as discharging. Charging (1) and discharging (2)
    follow nhurman/bluetti_mqtt and BluettiMonitor (Elite 200 V2).
    """

    IDLE = 0
    CHARGING = 1
    DISCHARGING = 2

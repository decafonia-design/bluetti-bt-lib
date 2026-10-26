from enum import Enum, unique


@unique
class ChargingPriority(Enum):
    """Charger 2 "Priority Charging" (bits 4-5 of register 15625)."""

    BLUETTI_PRODUCTS = 1
    PORTABLE_POWER_STATION = 2

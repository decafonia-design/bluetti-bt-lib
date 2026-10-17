from typing import Any, Optional

from . import UIntField


class NumberField(UIntField):
    """An unsigned integer register that the user can write back to the device.

    Adds write support on top of UIntField's parse/min/max handling so
    settings such as the AC300 SOC charge range (registers 3015/3016)
    can be exposed as adjustable numbers rather than read-only sensors.

    ``step`` is the increment the device accepts (e.g. 5 for a 0-100
    range in 5% steps). It is exposed so clients such as Home Assistant
    can build matching number entities, and it is enforced on write so a
    caller cannot submit an off-step value.
    """

    def __init__(
        self,
        name,
        address: int,
        multiplier: float = 1,
        min: Optional[int] = None,
        max: Optional[int] = None,
        step: Optional[int] = None,
    ):
        super().__init__(name, address, multiplier, min, max)
        self.step = step

    def is_writeable(self) -> bool:
        return True

    def allowed_write_type(self, value: Any) -> bool:
        # bool is a subclass of int; reject it so True/False are not
        # silently written as 1/0 to a numeric register.
        return isinstance(value, int) and not isinstance(value, bool)

from typing import Any

from . import UIntField


class NumberField(UIntField):
    """An unsigned integer register that the user can write back to the device.

    Adds write support on top of UIntField's parse/min/max handling so
    settings such as the AC300 SOC charge range (registers 3015/3016)
    can be exposed as adjustable numbers rather than read-only sensors.
    """

    def is_writeable(self) -> bool:
        return True

    def allowed_write_type(self, value: Any) -> bool:
        # bool is a subclass of int; reject it so True/False are not
        # silently written as 1/0 to a numeric register.
        return isinstance(value, int) and not isinstance(value, bool)

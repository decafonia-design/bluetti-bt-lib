import struct

from . import FieldName, UIntField


class OffsetIntField(UIntField):
    """An unsigned register minus a fixed offset.

    BLUETTI stores battery temperatures as degrees Celsius plus 40, so 54 is
    14 degrees and the register never has to go negative.
    """

    def __init__(
        self,
        name: FieldName,
        address: int,
        offset: int,
        min: int | None = None,
        max: int | None = None,
    ):
        super().__init__(name, address, 1, min, max)
        self.offset = offset

    def parse(self, data: bytes) -> int:
        return struct.unpack("!H", data)[0] - self.offset

    def in_range(self, value: int) -> bool:
        # Unlike UIntField, a value below zero is fine here: frost in a parked van.
        if self.min is not None and self.min > value:
            return False
        if self.max is not None and self.max < value:
            return False
        return True

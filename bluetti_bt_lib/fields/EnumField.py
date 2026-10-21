import struct
from enum import Enum
from typing import Any, Type, TypeVar

from . import DeviceField, FieldName


E = TypeVar("E", bound=Enum)


class EnumField(DeviceField):
    def __init__(
        self,
        name: FieldName,
        address: int,
        e: Type[E],
        verification_delay: float | None = None,
    ):
        super().__init__(name, address, 1, verification_delay)
        self.e = e

    def to_option(self, value: Any) -> E | None:
        """Return the option a requested value refers to, or None if none does.

        Callers reach this field three ways: Home Assistant names the option,
        a read-back parses to the Enum member, and the tools pass the raw
        number. Normalising here means a write and the check of that write
        describe the same option.
        """
        if isinstance(value, self.e):
            return value

        try:
            return self.e[value] if isinstance(value, str) else self.e(value)
        except (KeyError, ValueError):
            return None

    def parse(self, data: bytes) -> E | None:
        val = struct.unpack("!H", data)[0]

        if val not in [e.value for e in self.e]:
            return None

        return self.e(val)

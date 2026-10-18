from enum import Enum
from typing import Any, Type, TypeVar

from . import EnumField, FieldName


E = TypeVar("E", bound=Enum)


class SelectField(EnumField):
    def __init__(
        self,
        name: FieldName,
        address: int,
        e: Type[E],
        # Devices apply a select write slowly, so verification waits longer
        # than the default. A profile can still pass its own delay.
        verification_delay: float | None = 2.0,
    ):
        super().__init__(name, address, e, verification_delay)

    def is_writeable(self):
        return True

    def allowed_write_type(self, value: Any) -> bool:
        return isinstance(value, self.e)

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
        # Selects are written like any other control: the writer's default
        # verification window covers how slowly a station reflects them.
        verification_delay: float | None = None,
    ):
        super().__init__(name, address, e, verification_delay)

    def is_writeable(self):
        return True

    def allowed_write_type(self, value: Any) -> bool:
        return isinstance(value, self.e)

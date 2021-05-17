from tortoise.fields.base import Field
from typing import List, Any, Optional, Union, Type
from tortoise.models import Model
from enum import Enum
import inspect


class BigIntArrayField(Field, list):
    SQL_TYPE = "bigint[]"

    def to_db_value(self, value: Any, instance: Union[Type[Model], Model]) -> Any:
        return value

    def to_python_value(self, value: Any) -> Optional[List[int]]:
        return value


class CharVarArrayField(Field, list):
    SQL_TYPE = "character varying[]"

    def to_db_value(self, value: Any, instance: Union[Type[Model], Model]) -> Any:
        return value

    def to_python_value(self, value: Any) -> Optional[List[int]]:
        return value


# class EnumArrayField(Field, str):
#     def __init__(self, enum_class: Enum, **kwargs: Any) -> None:
#         self.enum_class = enum_class
#         super().__init__(**kwargs)

#     SQL_TYPE = "varchar[]"

#     def to_db_value(self, value: Any, instance: "Union[Type[Model], Model]") -> Any:
#         if inspect.isfunction(value):
#             value = value()
#         return [val.value for val in value]

#     def to_python_value(self, value: Any) -> Any:
#         return [getattr(self.enum_class, val) for val in value]


class EnumArrayField(Field, str):
    def __init__(self, enum_class: Enum, **kwargs: Any) -> None:
        self.enum_class = enum_class
        super().__init__(**kwargs)

    SQL_TYPE = "varchar[]"

    def to_db_value(self, value: Any, instance: "Union[Type[Model], Model]") -> Any:
        if inspect.isfunction(value):
            value = value()
            return [str(val.value) for val in value]

    def to_python_value(self, value: Any) -> Any:
        return [self.enum_class(val) for val in value]

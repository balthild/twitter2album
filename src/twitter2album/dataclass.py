import dataclasses
import json
from typing import Any, Self


class DataclassExt:
    def replace(self, **kwargs) -> Self:
        return dataclasses.replace(self, **kwargs)  # type: ignore

    def serialize(self) -> dict:
        return dataclasses.asdict(self)  # type: ignore

    @classmethod
    def deserialize(cls, values: dict) -> Self:
        if not dataclasses.is_dataclass(cls):
            raise ValueError(f'{cls.__name__} must be a dataclass')

        args = [
            deserialize_field(field, values[field.name])  #
            for field in dataclasses.fields(cls)
        ]

        return cls(*args)

    def to_json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def from_json(cls, data: str) -> Self:
        return cls.deserialize(json.loads(data))


def deserialize_field(field: dataclasses.Field, value: Any):
    match field.type:
        case type() if issubclass(field.type, DataclassExt):
            return field.type.deserialize(value)
        case _:
            return value

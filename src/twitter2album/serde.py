import dataclasses
import json
from typing import Any, Self


class SerdeDataclass:
    def replace(self, **kwargs) -> Self:
        return dataclasses.replace(self, **kwargs)

    def serialize(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def deserialize(cls, values: dict) -> Self:
        if not dataclasses.is_dataclass(cls):
            raise ValueError(f"{cls.__name__} must be a dataclass")

        args = [
            deserialize_field(field, values[field.name])
            for field in dataclasses.fields(cls)
        ]

        return cls(*args)

    def to_json(self) -> str:
        return json.dumps(self.serialize())

    @classmethod
    def from_json(cls, data: str) -> str:
        return cls.deserialize(json.loads(data))


def deserialize_field(field: dataclasses.Field, value: Any):
    if issubclass(field.type, SerdeDataclass):
        return field.type.deserialize(value)
    return value

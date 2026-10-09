import tomllib
from dataclasses import dataclass
from typing import Literal, Self

import serde


@serde.serde
@dataclass(frozen=True)
class Log:
    type Level = Literal['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    level: Level = serde.field(default='DEBUG', deserializer=lambda x: x.upper())


@serde.serde
@dataclass(frozen=True)
class Telegram:
    api_id: int
    api_hash: str
    bot_token: str
    allow_chats: list[int]


@serde.serde
@dataclass(frozen=True)
class Config:
    telegram: Telegram
    log: Log = serde.field(default_factory=Log)

    @classmethod
    def load(cls) -> Self:
        with open('./config.toml', 'rb') as f:
            return serde.from_dict(cls, tomllib.load(f))

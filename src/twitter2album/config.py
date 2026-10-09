import tomllib
from dataclasses import dataclass
from typing import Self

import serde


@serde.serde
@dataclass(frozen=True)
class Log:
    level: str = serde.field(default='DEBUG', deserializer=lambda x: x.upper())


@serde.serde
@dataclass(frozen=True)
class Telegram:
    api_id: int
    api_hash: str
    bot_token: str
    chat_whitelist: list[int]


@serde.serde
@dataclass(frozen=True)
class Config:
    log: Log
    telegram: Telegram

    @classmethod
    def load(cls) -> Self:
        with open('./config.toml', 'rb') as f:
            return serde.from_dict(cls, tomllib.load(f))

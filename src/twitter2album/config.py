from dataclasses import dataclass
from typing import Self

import tomli

from twitter2album.dataclass import DataclassExt


@dataclass(frozen=True)
class Telegram(DataclassExt):
    api_id: str
    api_hash: str
    bot_token: str
    chat_whitelist: list[int]
    forward_to: int


@dataclass(frozen=True)
class Twitter(DataclassExt):
    username: str
    cookies: str


@dataclass(frozen=True)
class Bsky(DataclassExt):
    username: str
    password: str


@dataclass(frozen=True)
class Domains(DataclassExt):
    twitter = (
        'twitter.com',
        'x.com',
        'fixvx.com',
        'fixupx.com',
        'vxtwitter.com',
        'fxtwitter.com',
    )

    bsky = ('bsky.app',)


@dataclass(frozen=True)
class Config(DataclassExt):
    telegram: Telegram
    twitter: Twitter
    bsky: Bsky

    domains = Domains()

    @classmethod
    def load(cls) -> Self:
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)
            return cls.deserialize(values)

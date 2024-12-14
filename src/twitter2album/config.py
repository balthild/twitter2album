from dataclasses import dataclass
from typing import Self

import tomli

from twitter2album.serde import SerdeDataclass


@dataclass(frozen=True)
class Telegram(SerdeDataclass):
    api_id: str
    api_hash: str
    bot_token: str
    chat_whitelist: list[int]
    forward_to: int


@dataclass(frozen=True)
class Twitter(SerdeDataclass):
    username: str
    password: str


@dataclass(frozen=True)
class Bsky(SerdeDataclass):
    username: str
    password: str


@dataclass(frozen=True)
class Domains(SerdeDataclass):
    twitter = [
        'twitter.com',
        'x.com',
        'fixvx.com',
        'fixupx.com',
        'vxtwitter.com',
        'fxtwitter.com',
    ]

    bsky = [
        'bsky.app',
    ]


@dataclass(frozen=True)
class Config(SerdeDataclass):
    telegram: Telegram
    twitter: Twitter
    bsky: Bsky

    domains = Domains()

    def load() -> Self:
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)
            return Config.deserialize(values)

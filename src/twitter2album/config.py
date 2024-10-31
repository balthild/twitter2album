from dataclasses import dataclass
from typing import Self

import tomli


@dataclass(frozen=True)
class Telegram:
    api_id: str
    api_hash: str
    bot_token: str
    chat_whitelist: list[int]

    def deserialize(values: dict) -> Self:
        return Telegram(
            api_id=values['api_id'],
            api_hash=values['api_hash'],
            bot_token=values['bot_token'],
            chat_whitelist=values['chat_whitelist'],
        )


@dataclass(frozen=True)
class Twitter:
    username: str
    password: str

    def deserialize(values: dict) -> Self:
        return Twitter(
            username=values['username'],
            password=values['password'],
        )


@dataclass(frozen=True)
class Bsky:
    username: str
    password: str

    def deserialize(values: dict) -> Self:
        return Bsky(
            username=values['username'],
            password=values['password'],
        )


@dataclass(frozen=True)
class Domains:
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
class Config:
    telegram: Telegram
    twitter: Twitter
    bsky: Bsky

    domains = Domains()

    def deserialize(values: dict) -> Self:
        return Config(
            telegram=Telegram.deserialize(values['telegram']),
            twitter=Twitter.deserialize(values['twitter']),
            bsky=Bsky.deserialize(values['bsky']),
        )

    def load() -> Self:
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)
            return Config.deserialize(values)

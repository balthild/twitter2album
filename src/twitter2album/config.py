from dataclasses import dataclass
from typing import Self

import tomli


@dataclass(frozen=True)
class _Telegram:
    api_id: str = None
    api_hash: str = None
    bot_token: str = None
    chat_whitelist: list[int] = None

    def deserialize(values: dict) -> Self:
        return _Telegram(
            api_id=values['api_id'],
            api_hash=values['api_hash'],
            bot_token=values['bot_token'],
            chat_whitelist=values['chat_whitelist'],
        )


@dataclass(frozen=True)
class _Twitter:
    username: str = None
    password: str = None

    def deserialize(values: dict) -> Self:
        return _Twitter(
            username=values['username'],
            password=values['password'],
        )


@dataclass(frozen=True)
class _Bsky:
    username: str = None
    password: str = None

    def deserialize(values: dict) -> Self:
        return _Bsky(
            username=values['username'],
            password=values['password'],
        )


@dataclass(frozen=True)
class _Domains:
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
    telegram: _Telegram
    twitter: _Twitter
    bsky: _Bsky

    domains = _Domains()

    def deserialize(values: dict) -> Self:
        return Config(
            telegram=_Telegram.deserialize(values['telegram']),
            twitter=_Twitter.deserialize(values['twitter']),
            bsky=_Bsky.deserialize(values['bsky']),
        )

    def load() -> Self:
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)
            return Config.deserialize(values)

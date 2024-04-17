from dataclasses import dataclass

import tomli


@dataclass
class Telegram:
    api_id: str = None
    api_hash: str = None
    bot_token: str = None
    chat_whitelist: list[int] = None


@dataclass
class Twitter:
    username: str = None
    password: str = None


@dataclass
class Config:
    telegram: Telegram
    twitter: Twitter

    def load():
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)

            return Config(
                telegram=Telegram(
                    api_id=values['telegram']['api_id'],
                    api_hash=values['telegram']['api_hash'],
                    bot_token=values['telegram']['bot_token'],
                    chat_whitelist=values['telegram']['chat_whitelist'],
                ),
                twitter=Twitter(
                    username=values['twitter']['username'],
                    password=values['twitter']['password'],
                ),
            )

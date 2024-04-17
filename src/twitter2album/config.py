from dataclasses import dataclass

import tomli

@dataclass
class Config:
    telegram_api_id: str = None
    telegram_api_hash: str = None
    telegram_bot_token: str = None
    telegram_chat_whitelist: list[int] = None

    twitter_username: str = None
    twitter_password: str = None

    def load():
        with open('./config.toml', 'rb') as f:
            values = tomli.load(f)
            return Config(**values)

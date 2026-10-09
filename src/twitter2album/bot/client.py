from pyrogram import Client

from twitter2album.config import Config
from twitter2album.const import C


class BotClient(Client):
    def __init__(self, config: Config):
        super().__init__(
            name=config.telegram.bot_token.split(':')[0],
            bot_token=config.telegram.bot_token,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            workdir=str(C.dirs.pyrogram),
        )

    def __aenter__(self):
        C.dirs.pyrogram.mkdir(parents=True, exist_ok=True)
        return super().__aenter__()

    def __aexit__(self, *args):
        return super().__aexit__(*args)

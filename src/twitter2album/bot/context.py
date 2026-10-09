import sys
from typing import Final, Self

from aiohttp import ClientSession
from loguru import logger

from twitter2album.bot.client import BotClient
from twitter2album.config import Config
from twitter2album.db.store import Store


class Context:
    def __init__(self, config: Config):
        self.config: Final = config
        self.store: Final = Store()
        self.http: Final = ClientSession()
        self.bot: Final = BotClient(config)

        # import here to avoid circular import error
        from twitter2album.bot.handler import ButtonHandler, ShareHandler, TextHandler

        self.bot.add_handler(TextHandler(self))
        self.bot.add_handler(ButtonHandler(self))
        self.bot.add_handler(ShareHandler(self))

        # twscrape overrides log level in side effects
        logger.remove()
        logger.add(sys.stderr, level=config.log.level)

        if config.log.level == 'TRACE':
            logger.trace('TRACE mode enabled. Unhandled raw updates will be printed')
            self.bot.on_raw_update()(self.trace)

    async def __aenter__(self) -> Self:
        await self.store.__aenter__()
        await self.http.__aenter__()
        await self.bot.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.bot.__aexit__(*args)
        await self.http.__aexit__(*args)
        await self.store.__aexit__(*args)

    def trace(self, client, update, *args, **kwargs):
        from twitter2album.utils import dbg

        dbg(update, depth=12)

import os
from typing import Self

from aiohttp import ClientSession
from pyrogram import Client

from twitter2album.bsky import BskyClient
from twitter2album.config import Config
from twitter2album.twitter import TwitterClient


class Context:
    def __init__(self):
        self.config = Config.load()
        self.twitter = TwitterClient(self.config)
        self.bsky = BskyClient(self.config)
        self.http = ClientSession()

        self.bot = Client(
            name=self.config.telegram.bot_token.split(':')[0],
            bot_token=self.config.telegram.bot_token,
            api_id=self.config.telegram.api_id,
            api_hash=self.config.telegram.api_hash,
            workdir=os.getcwd(),
        )

        from twitter2album.bot.button import ButtonHandler
        from twitter2album.bot.text import TextHandler
        self.bot.add_handler(TextHandler(self))
        self.bot.add_handler(ButtonHandler(self))

    async def __aenter__(self) -> Self:
        await self.twitter.__aenter__()
        await self.bsky.__aenter__()
        await self.http.__aenter__()
        await self.bot.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.bot.__aexit__(*args)
        await self.twitter.__aexit__(*args)
        await self.bsky.__aexit__(*args)
        await self.http.__aexit__(*args)

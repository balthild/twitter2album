from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from typing import Any, Final
from urllib.parse import urlparse

from loguru import logger
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.filters import Filter
from pyrogram.handlers.handler import Handler
from pyrogram.types import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMedia,
    InputMediaPhoto,
    InputMediaVideo,
)

from twitter2album.bot.context import Context
from twitter2album.bsky import BskyPostEx
from twitter2album.error import UserException
from twitter2album.twitter import TweetEx


class ContextualHandler(ABC, Handler):
    def __init__(self, ctx: Context, filters: Filter | None = None):
        super().__init__(self.callback, filters)  # type: ignore
        self.ctx: Final = ctx

    async def callback(self, bot: Client, *args):
        try:
            handler = self.inner(self.ctx, *args)
            await handler.handle()
        except UserException as e:
            await handler.notify(str(e))
        except Exception as e:  # noqa: BLE001
            logger.error(str(e))
            traceback.print_exc()
            await handler.notify('Internal Error')

    @abstractmethod
    def inner(self, ctx: Context, *args) -> ContextualHandlerInner: ...


class ContextualHandlerInner(ABC):
    def __init__(self, ctx: Context):
        self.config: Final = ctx.config
        self.twitter: Final = ctx.twitter
        self.bsky: Final = ctx.bsky
        self.http: Final = ctx.http
        self.bot: Final = ctx.bot

    @abstractmethod
    async def notify(self, text: str): ...

    @abstractmethod
    async def handle(self): ...

    async def get_post(self, url: str):
        parsed = urlparse(url)
        if parsed.netloc in self.config.domains.twitter:
            return await self.twitter.get_tweet_ex(parsed)
        elif parsed.netloc in self.config.domains.bsky:
            return await self.bsky.get_post_ex(parsed)
        else:
            raise UserException('Unrecognized URL')

    async def get_album(self, post: BskyPostEx | TweetEx) -> list[InputMedia]:
        album = []
        for photo in post.photos():
            album.append(InputMediaPhoto(photo))
        for video in post.videos():
            album.append(InputMediaVideo(video))
        for gif in post.gifs():
            album.append(InputMediaVideo(gif, disable_content_type_detection=True))

        return album

    async def send_album(self, chat: Chat, post: BskyPostEx | TweetEx, album: list):
        url = post.url()
        content = post.render()

        source = f'<a href="{url}">source</a>'
        sep = '\n' if '\n' in content else ' '
        album[0].caption = f'{content}{sep}{source}'.strip()
        album[0].parse_mode = ParseMode.HTML

        [message] = await self.bot.send_media_group(chat.id, album)

        await message.edit_reply_markup(self.get_action_buttons())

    def get_action_buttons(self, old: InlineKeyboardMarkup | Any = None):
        if not isinstance(old, InlineKeyboardMarkup):
            actions = ['Silent', 'Forward']
        else:
            transitions = {
                'Silent': 'Caption',
                'Caption': 'Silent',
                'Forward': 'Forwarded',
                'Forwarded': 'Forwarded',
            }
            actions = [
                transitions[button.text]
                for line in old.inline_keyboard
                for button in line
                if button.text in transitions
            ]

        buttons = [
            InlineKeyboardButton(action, callback_data=action)  #
            for action in actions
        ]

        return InlineKeyboardMarkup([buttons])

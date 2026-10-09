from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import cached_property
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
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from twitter2album.api import AbstractPost, BskyClient, TwitterClient
from twitter2album.bot.context import Context
from twitter2album.bot.types import Account
from twitter2album.const import C
from twitter2album.db.user import User
from twitter2album.error import AbortException, StateException, UserException


class ContextualHandler(ABC, Handler):
    """
    A handler that handles all messages along the whole lifetime of the bot.
    """

    def __init__(self, ctx: Context, filters: Filter | None = None):
        super().__init__(self.handle, filters=filters)  # type: ignore
        self.ctx: Final = ctx

    async def handle(self, bot: Client, *args):
        try:
            responder = self.responder(self.ctx, *args)
            await responder.handle()
        except AbortException:
            return
        except StateException as e:
            responder.user.state = None
            responder.user.save()
            await responder.notify(str(e))
        except UserException as e:
            await responder.notify(str(e))
        except Exception as e:  # noqa: BLE001
            logger.error(str(e))
            traceback.print_exc()
            await responder.notify('Internal Error')

    @abstractmethod
    def responder(self, ctx: Context, *args) -> ContextualResponder: ...


class ContextualResponder(ABC):
    """
    A handler for a specific incoming message.
    """

    def __init__(self, ctx: Context, sender: int):
        self.ctx: Final = ctx
        self.config: Final = ctx.config
        self.http: Final = ctx.http
        self.bot: Final = ctx.bot
        self.sender: Final = sender

    @cached_property
    def user(self) -> User:
        return User.resolve(self.sender)

    @cached_property
    def twitter(self) -> TwitterClient:
        return TwitterClient(self.user._id)

    @cached_property
    def bsky(self) -> BskyClient:
        return BskyClient(self.user._id)

    @abstractmethod
    async def notify(self, text: str): ...

    @abstractmethod
    async def handle(self): ...

    def skipped(self, chat: Chat) -> bool:
        return chat.id == self.user.forward

    def unknown(self, chat: Chat) -> bool:
        return chat.id not in self.config.telegram.allow_chats

    async def accounts(self) -> Sequence[Account]:
        accounts = []

        for handle in await self.twitter.handles():
            accounts.append(Account('twitter', handle, handle))

        for did, credentials in self.user.bsky.items():
            accounts.append(Account('bsky', credentials.handle, did))

        return accounts

    async def get_post(self, url: str) -> AbstractPost:
        parsed = urlparse(url)
        if parsed.netloc in C.domains.twitter:
            await self.twitter.authenticate()
            return await self.twitter.get_tweet_ex(parsed)
        elif parsed.netloc in C.domains.bsky:
            await self.bsky.authenticate()
            return await self.bsky.get_post_ex(parsed)
        else:
            raise UserException('Unrecognized URL')

    async def get_media(self, post: AbstractPost) -> list[InputMediaPhoto | InputMediaVideo]:
        media = []
        for photo in post.photos():
            media.append(InputMediaPhoto(photo))
        for video in post.videos():
            media.append(InputMediaVideo(video))
        for gif in post.gifs():
            media.append(InputMediaVideo(gif, disable_content_type_detection=True))

        return media

    async def send_album(
        self,
        chat: Chat,
        post: AbstractPost,
        media: list[InputMediaPhoto | InputMediaVideo],
        markup: InlineKeyboardMarkup | None,
    ) -> list[Message]:
        url = post.url()
        content = post.render()

        source = f'<a href="{url}">source</a>'
        sep = '\n' if '\n' in content else ' '
        media[0].caption = f'{content}{sep}{source}'.strip()
        media[0].parse_mode = ParseMode.HTML

        album = await self.bot.send_media_group(chat.id, [*media])

        if markup is not None:
            if len(album) == 1:
                await album[0].edit_reply_markup(markup)
            else:
                reply = await album[0].reply(f'album={album[0].id}', quote=True)
                await reply.edit_reply_markup(markup)

        return album

    def markup_single(self, old: InlineKeyboardMarkup | Any = None):
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

    def markup_import(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Silent', callback_data='import:silent'),
                InlineKeyboardButton('Caption', callback_data='import:caption'),
            ],
            [
                InlineKeyboardButton('Skip', callback_data='import:skip'),
                InlineKeyboardButton('Unbookmark', callback_data='import:unbookmark'),
            ],
            [
                InlineKeyboardButton('Forward & Unbookmark', callback_data='import:commit'),
            ],
        ])

    def html_caption(self, post: AbstractPost) -> str:
        source = self.html_source(post.url())
        content = post.render()
        sep = '\n' if '\n' in content else ' '

        return f'{content}{sep}{source}'.strip()

    def html_source(self, url: str) -> str:
        return f'<a href="{url}">source</a>'

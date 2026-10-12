from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator, Sequence
from functools import cached_property
from typing import Any, Final
from urllib.parse import urlparse

from loguru import logger
from PIL import UnidentifiedImageError
from PIL.Image import Image
from PIL.Image import open as open_image
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.filters import Filter
from pyrogram.handlers.handler import Handler
from pyrogram.types import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAnimation,
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

type InputMediaAllowed = InputMediaPhoto | InputMediaVideo | InputMediaAnimation
type InputMediaMapped = InputMediaPhoto | InputMediaVideo


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

    async def get_media(self, post: AbstractPost) -> list[InputMediaAllowed]:
        media = []
        for photo in post.photos():
            media.append(InputMediaPhoto(photo))
        for video in post.videos():
            media.append(InputMediaVideo(video))
        for gif in post.gifs():
            media.append(InputMediaAnimation(gif))

        return media

    def map_media(self, media: list[InputMediaAllowed]) -> Iterator[InputMediaMapped]:
        for item in media:
            if isinstance(item, InputMediaAnimation):
                yield InputMediaVideo(item.media, disable_content_type_detection=True)
            else:
                yield item

    async def fetch_images(self, post: AbstractPost) -> AsyncIterator[Image]:
        @self.ctx.cache.disk.memoize_async(name='t2a:media:fetch')
        async def fetch(url: str) -> bytes:
            response = await self.http.get(url)
            if response.status // 100 != 2:
                raise UserException(f'{response.status} {response.reason} while fetching {url}')
            return await response.read()

        for url in post.photos():
            try:
                yield open_image(await fetch(url))
            except UnidentifiedImageError:
                raise UserException(f'Failed to decode image data from {url}')

    async def send_album(
        self,
        chat: Chat,
        post: AbstractPost,
        media: list[InputMediaAllowed],
        markup: InlineKeyboardMarkup = None,  # type: ignore
    ) -> list[Message]:
        match media:
            case [InputMediaPhoto() as photo]:
                message = await self.bot.send_photo(
                    chat.id,
                    photo,
                    reply_markup=markup,
                    caption=self.html_caption(post),
                    parse_mode=ParseMode.HTML,
                )

                if message is None:
                    raise UserException('Failed to send media')
                return [message]

            case [InputMediaVideo() as video]:
                message = await self.bot.send_video(
                    chat.id,
                    video.media,
                    reply_markup=markup,
                    caption=self.html_caption(post),
                    parse_mode=ParseMode.HTML,
                )

                if message is None:
                    raise UserException('Failed to send media')
                return [message]

            case [InputMediaAnimation() as gif]:
                message = await self.bot.send_animation(
                    chat.id,
                    gif.media,
                    reply_markup=markup,
                    caption=self.html_caption(post),
                    parse_mode=ParseMode.HTML,
                )

                if message is None:
                    raise UserException('Failed to send media')
                return [message]

            case [*media]:
                media[0].caption = self.html_caption(post)
                media[0].parse_mode = ParseMode.HTML

                album = await self.bot.send_media_group(chat.id, [*self.map_media(media)])

                reply = await album[0].reply(f'album={album[0].id}', quote=True)
                await reply.edit_reply_markup(markup)

                if not album:
                    raise UserException('Failed to send media')
                return album

    def markup_manual(self):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Silent', callback_data='manual:silent'),
                InlineKeyboardButton('Caption', callback_data='manual:caption'),
            ],
            [
                InlineKeyboardButton('Forward', callback_data='manual:forward'),
            ],
        ])

    def markup_import(self, rid: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Silent', callback_data=f'import:silent:{rid}'),
                InlineKeyboardButton('Caption', callback_data=f'import:caption:{rid}'),
            ],
            [
                InlineKeyboardButton('Skip', callback_data=f'import:skip:{rid}'),
                InlineKeyboardButton('Unbookmark', callback_data=f'import:unbookmark:{rid}'),
            ],
            [
                InlineKeyboardButton('Forward & Unbookmark', callback_data=f'import:commit:{rid}'),
            ],
        ])

    def html_caption(self, post: AbstractPost) -> str:
        source = self.html_source(post.url())
        content = post.render()
        sep = '\n' if '\n' in content else ' '

        return f'{content}{sep}{source}'.strip()

    def html_source(self, url: str) -> str:
        return f'<a href="{url}">source</a>'

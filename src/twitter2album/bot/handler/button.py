from functools import cached_property
from typing import Final
from uuid import uuid4

from loguru import logger
from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.errors.rpc_error import RPCError
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery, Chat, Message

from twitter2album.api import TweetEx, parse_tweet_id
from twitter2album.bot.context import Context
from twitter2album.const import C
from twitter2album.db.skip import Skip
from twitter2album.db.state import (
    AskingImportAccount,
    AskingLoginHandle,
    AskingLoginPlatform,
    AskingLogoutAccount,
    Importing,
)
from twitter2album.error import StateException, UserException

from .base import ContextualHandler, ContextualResponder


class ButtonHandler(ContextualHandler, CallbackQueryHandler):
    def __init__(self, ctx: Context):
        super().__init__(ctx)

    def responder(self, ctx: Context, *args) -> ContextualResponder:
        return ButtonResponder(ctx, *args)


class ButtonResponder(ContextualResponder):
    def __init__(self, ctx: Context, query: CallbackQuery):
        super().__init__(ctx, query.from_user.id)
        self.query: Final = query

    @cached_property
    def message(self) -> Message:
        message = self.query.message
        quoted = message.reply_to_message

        if quoted is None:
            return message

        if message.text == f'album={quoted.id}':
            return quoted

        raise StateException()

    async def notify(self, text: str):
        await self.query.message.reply(text, parse_mode=ParseMode.MARKDOWN)

    async def handle(self):
        if self.skipped(self.message.chat):
            return
        if self.unknown(self.message.chat):
            return

        match self.query.data:
            case 'Silent':
                await self.handle_silent()
            case 'Caption':
                await self.handle_caption()
            case 'Forward' | 'Forwarded':
                await self.handle_forward()
            case str(data):
                await self.handle_state(data)

    async def handle_silent(self):
        url = self.extract_source_url()

        await self.message.edit_caption(
            self.html_source(url),
            parse_mode=ParseMode.HTML,
            reply_markup=self.markup_single(self.message.reply_markup),
        )
        await self.query.answer('Caption silenced')

    async def handle_caption(self):
        url = self.extract_source_url()
        post = await self.get_post(url)

        await self.message.edit_caption(
            self.html_caption(post),
            parse_mode=ParseMode.HTML,
            reply_markup=self.markup_single(self.message.reply_markup),
        )
        await self.query.answer('Caption rendered')

    async def handle_forward(self):
        target = self.user.forward
        if target is None:
            await self.query.answer()
            raise UserException('No forward target set. Use /forward to choose one')

        chat = self.message.chat
        album = await self.get_album(self.message)

        await self.bot.forward_messages(target, chat.id, [message.id for message in album])
        await self.query.answer('Forwarded')

    async def handle_state(self, data: str):
        match self.user.state:
            # auth
            case AskingLoginPlatform() if data.startswith('login:'):
                await self.handle_login_platform(data)
            case AskingLogoutAccount() if data.startswith('logout:'):
                await self.handle_logout_account(data)

            # import
            case AskingImportAccount() if data.startswith('import:account:'):
                await self.handle_import_account(data.removeprefix('import:account:'))
            case Importing() as state if data == f'import:silent:{state.rid}':
                await self.handle_import_silent(state)
            case Importing() as state if data == f'import:caption:{state.rid}':
                await self.handle_import_caption(state)
            case Importing() as state if data == f'import:skip:{state.rid}':
                await self.handle_import_skip(state)
            case Importing() as state if data == f'import:unbookmark:{state.rid}':
                await self.handle_import_unbookmark(state)
            case Importing() as state if data == f'import:commit:{state.rid}':
                await self.handle_import_commit(state)

            # leftover buttons from other import batches
            case _ if data.startswith('import:'):
                await self.handle_import_leftover()

            # unknown
            case _:
                raise StateException()

    async def handle_login_platform(self, data: str):
        match data.split(':', 1):
            case ['login', platform] if platform in C.platforms:
                self.user.state = AskingLoginHandle(platform=platform)
                self.user.save()
                await self.query.answer()
                await self.message.edit_text(f'Send your {C.platforms[platform]} handle.')

            case ['login', platform]:
                raise UserException(f'Unknown platform `{platform}`')

            case _:
                raise StateException('/login')

    async def handle_logout_account(self, data: str):
        match data.split(':', 2):
            case ['logout', 'twitter', handle]:
                await self.twitter.logout(handle)
                await self.query.answer()
                await self.message.edit_text(f'Logged out of {C.platforms["twitter"]} as {handle}')

            case ['logout', 'bsky', did] if did in self.user.bsky:
                credentials = self.user.bsky.pop(did)
                self.user.save()
                await self.query.answer()
                await self.message.edit_text(f'Logged out of {C.platforms["bsky"]} as {credentials.handle}')

            case _:
                raise StateException('/logout')

    async def handle_import_account(self, handle: str):
        if handle not in await self.twitter.handles():
            raise StateException('/import')

        rid = uuid4().hex
        self.ctx.cache.put(rid, self.twitter.bookmarks_of(handle))

        self.user.state = Importing(handle=handle, rid=rid)
        self.user.save()

        await self.query.answer()
        await self.message.edit_text(f'Importing bookmarks of {handle}')

        await self.import_advance(self.message.chat, rid, handle)

    async def handle_import_silent(self, state: Importing):
        url = self.extract_source_url()

        await self.message.edit_caption(
            self.html_source(url),
            parse_mode=ParseMode.HTML,
            reply_markup=self.markup_import(),
        )
        await self.query.answer()

    async def handle_import_caption(self, state: Importing):
        url = self.extract_source_url()
        post = await self.get_post(url)

        await self.message.edit_caption(
            self.html_caption(post),
            parse_mode=ParseMode.HTML,
            reply_markup=self.markup_import(),
        )
        await self.query.answer()

    async def handle_import_skip(self, state: Importing):
        chat = self.message.chat

        self.mark_skipped(self.extract_source_url())

        await self.query.answer('Skipped')
        await self.remove_buttons()
        await self.import_advance(chat, state.rid, state.handle)

    async def handle_import_unbookmark(self, state: Importing):
        url = self.extract_source_url()

        try:
            await self.twitter.remove_bookmark_of(state.handle, parse_tweet_id(url))
        except UserException as e:
            logger.warning('Failed to unbookmark {}: {}', url, e)
            await self.query.answer('Failed to unbookmark', show_alert=True)
        else:
            await self.query.answer('Unbookmarked')
            await self.import_advance(self.message.chat, state.rid, state.handle)

    async def handle_import_commit(self, state: Importing):
        target = self.user.forward
        if target is None:
            await self.query.answer()
            raise UserException('No forward target set. Use /forward to choose one')

        url = self.extract_source_url()
        chat = self.message.chat
        album = await self.get_album(self.message)

        await self.bot.forward_messages(target, chat.id, [message.id for message in album])

        try:
            await self.twitter.remove_bookmark_of(state.handle, parse_tweet_id(url))
        except UserException:
            await self.query.answer('Forwarded, but failed to unbookmark', show_alert=True)
        else:
            self.unmark_skipped(url)
            await self.query.answer('Forwarded and unbookmarked')
            await self.remove_buttons()
            await self.import_advance(chat, state.rid, state.handle)

    async def handle_import_leftover(self):
        await self.query.answer('These buttons are no longer relevant')
        await self.remove_buttons()

    def extract_source_url(self):
        if self.message.caption_entities:
            entity = self.message.caption_entities[-1]
            if entity.type == MessageEntityType.TEXT_LINK:
                start = entity.offset
                end = entity.offset + entity.length
                if self.message.caption[start:end] == 'source':
                    return entity.url

        raise UserException('Cannot find post source. Please send the source URL again')

    async def import_advance(self, chat: Chat, rid: str, handle: str):
        """
        Send the next bookmark worth showing, passing over the rest.
        """

        generator = self.ctx.cache.get(rid)
        if generator is None:
            generator = self.twitter.bookmarks_of(handle)
            self.ctx.cache.put(rid, generator)

        while True:
            try:
                tweet = await anext(generator)
            except StopAsyncIteration:
                await self.ctx.cache.discard(rid)
                self.user.reset_state()
                self.user.save()
                await self.bot.send_message(chat.id, 'No more bookmarks')
                return

            post = TweetEx(tweet)
            url = post.url()

            if self.is_skipped(url):
                continue

            try:
                media = await self.get_media(post)
            except UserException as e:
                # One unrenderable post should not abandon a whole run.
                logger.warning('Skipping {} during import: {}', url, e)
                continue

            if not media:
                continue

            await self.send_album(chat, post, media, self.markup_import())
            return

    async def get_album(self, message: Message) -> list[Message]:
        """
        The messages forming the album `message` belongs to.

        Telegram gives a single-item album no media group id, so `get_media_group`
        rejects it and the message is the whole album.
        """

        try:
            return await self.bot.get_media_group(message.chat.id, message.id)
        except ValueError:
            return [message]

    async def remove_buttons(self):
        message = self.query.message
        try:
            await message.edit_reply_markup()
        except RPCError as e:
            logger.warning('Failed to remove buttons from message {}: {}', message.id, e)

    def is_skipped(self, url: str) -> bool:
        return Skip.find(self.user._id, url) is not None

    def mark_skipped(self, url: str):
        Skip.add(self.user._id, url)

    def unmark_skipped(self, url: str):
        Skip.remove(self.user._id, url)

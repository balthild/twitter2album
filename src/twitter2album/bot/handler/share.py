from typing import Final

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.types import ChatShared, Message, ReplyKeyboardRemove

from twitter2album.bot.context import Context
from twitter2album.error import UserException

from .base import ContextualHandler, ContextualResponder


class ShareHandler(ContextualHandler, MessageHandler):
    def __init__(self, ctx: Context):
        super().__init__(ctx, filters=filters.chat_shared)

    def responder(self, ctx: Context, *args) -> ContextualResponder:
        return ShareResponder(ctx, *args)


class ShareResponder(ContextualResponder):
    def __init__(self, ctx: Context, message: Message):
        super().__init__(ctx, message.from_user.id)
        self.message: Final = message

    async def notify(self, text: str):
        await self.message.reply(text, parse_mode=ParseMode.MARKDOWN)

    async def handle(self):
        if self.message.chat_shared:
            return await self.handle_chat_shared(self.message.chat_shared)

    async def handle_chat_shared(self, shared: ChatShared):
        if len(shared.chats) != 1:
            raise UserException(f'Expected exactly one chat, found {len(shared.chats)}')

        self.user.forward = shared.chats[0].id
        self.user.save()

        await self.message.reply(
            'Forwarding chat updated',
            reply_markup=ReplyKeyboardRemove(),
        )

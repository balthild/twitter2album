import re

from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from twitter2album.bot.context import Context
from twitter2album.bot.handler import ContextualHandler
from twitter2album.error import UserException


class TextHandler(ContextualHandler, MessageHandler):
    def __init__(self, ctx: Context):
        super().__init__(ctx)

    async def args(self, message: Message):
        self.message = message

    async def notify(self, text: str):
        await self.message.reply(text)

    async def handle(self):
        if self.message.chat.id == self.config.telegram.forward_to:
            return
        if self.message.chat.id not in self.config.telegram.chat_whitelist:
            await self.handle_chatid()
            return

        match self.message.text.split():
            case ['/chatid']:
                await self.handle_chatid()
            case ['/relogin']:
                await self.handle_relogin()
            case [url, *pick]:
                await self.handle_media(url, pick)

    async def handle_chatid(self):
        await self.message.reply(f'Chat ID: {self.message.chat.id}')

    async def handle_relogin(self):
        success, failed = await self.twitter.relogin()
        await self.message.reply(f'Success: {success}\nFailed: {failed}')

    async def handle_media(self, url: str, pick: list[str] = []):
        post = await self.get_post(url)
        album = await self.get_album(post)

        subset = []
        for expr in pick:
            if not expr:
                continue
            elif re.match(r'^\d+$', expr):
                subset.append(int(expr))
            elif re.match(r'^\d+-\d+$', expr):
                [start, end] = [int(x) for x in expr.split('-')]
                subset.extend(range(start, end + 1))
            else:
                raise UserException(
                    'Invalid picking expression. Example: 1 3-4')

        count = len(album)
        if subset:
            album = [medium for i, medium in enumerate(album) if i+1 in subset]
            if not album:
                raise UserException(f'None of the {count} media is picked')

        await self.send_album(self.message.chat, post, album)

from pyrogram.enums import MessageEntityType
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery

from twitter2album.bot.context import Context
from twitter2album.bot.handler import ContextualHandler
from twitter2album.error import UserException


class ButtonHandler(ContextualHandler, CallbackQueryHandler):
    def __init__(self, ctx: Context):
        super().__init__(ctx)

    async def args(self, query: CallbackQuery):
        self.query = query
        self.message = query.message

    async def notify(self, text: str):
        await self.message.reply(text)

    async def handle(self):
        if self.message.chat.id == self.config.telegram.forward_to:
            return
        if self.message.chat.id not in self.config.telegram.chat_whitelist:
            return

        match self.query.data:
            case 'Silent':
                await self.handle_silent()
            case 'Caption':
                await self.handle_caption()
            case 'Forward' | 'Forwarded':
                await self.handle_forward()
            case _:
                await self.query.answer('Unrecognized Button')

    async def handle_silent(self):
        url = self.get_source_url()
        source = f'<a href="{url}">source</a>'
        buttons = self.get_action_buttons(self.message.reply_markup)
        await self.message.edit_caption(source, reply_markup=buttons)

    async def handle_caption(self):
        url = self.get_source_url()
        post = await self.get_post(url)

        url = post.url()
        source = f'<a href="{url}">source</a>'
        content = post.render()
        sep = '\n' if '\n' in content else ' '

        caption = f'{content}{sep}{source}'.strip()
        buttons = self.get_action_buttons(self.message.reply_markup)

        await self.message.edit_caption(caption, reply_markup=buttons)

    async def handle_pick(self):
        await self.query.answer('TODO: pick')

    async def handle_forward(self):
        await self.message.forward(self.config.telegram.forward_to)
        await self.query.answer('Forwarded')

    def get_source_url(self):
        if self.message.caption_entities:
            entity = self.message.caption_entities[-1]
            if entity.type == MessageEntityType.TEXT_LINK:
                start = entity.offset
                end = entity.offset + entity.length
                if self.message.caption[start:end] == 'source':
                    return entity.url

        raise UserException(
            'Cannot find post source. Please send the source URL again')

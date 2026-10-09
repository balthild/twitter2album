from typing import Final

from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import CallbackQuery, Message

from twitter2album.bot.context import Context
from twitter2album.const import C
from twitter2album.db.state import AskingLoginHandle, AskingLoginPlatform, AskingLogoutAccount
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

    @property
    def message(self) -> Message:
        return self.query.message

    async def notify(self, text: str):
        await self.message.reply(text, parse_mode=ParseMode.MARKDOWN)

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
        target = self.user.forward
        if target is None:
            await self.query.answer()
            raise UserException('No forward target set. Use /forward to choose one')

        await self.message.forward(target)
        await self.query.answer('Forwarded')

    async def handle_state(self, data: str):
        match self.user.state:
            case AskingLoginPlatform() if data.startswith('login:'):
                await self.handle_login_platform(data)
            case AskingLogoutAccount() if data.startswith('logout:'):
                await self.handle_logout_account(data)
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

    def get_source_url(self):
        if self.message.caption_entities:
            entity = self.message.caption_entities[-1]
            if entity.type == MessageEntityType.TEXT_LINK:
                start = entity.offset
                end = entity.offset + entity.length
                if self.message.caption[start:end] == 'source':
                    return entity.url

        raise UserException('Cannot find post source. Please send the source URL again')

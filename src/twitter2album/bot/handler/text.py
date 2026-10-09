import re
from collections.abc import Sequence
from typing import Final

from loguru import logger
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler
from pyrogram.types import (
    ChatPrivileges,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    Message,
    ReplyKeyboardMarkup,
)

from twitter2album.bot.context import Context
from twitter2album.const import C
from twitter2album.db.state import (
    AskingImportAccount,
    AskingLoginHandle,
    AskingLoginPlatform,
    AskingLoginSecret,
    AskingLogoutAccount,
    Importing,
)
from twitter2album.db.user import BskyCredentials
from twitter2album.error import StateException, UserException

from .base import ContextualHandler, ContextualResponder


class TextHandler(ContextualHandler, MessageHandler):
    def __init__(self, ctx: Context):
        super().__init__(ctx, filters=filters.text)

    def responder(self, ctx: Context, *args) -> ContextualResponder:
        return TextResponder(ctx, *args)


class TextResponder(ContextualResponder):
    def __init__(self, ctx: Context, message: Message):
        super().__init__(ctx, message.from_user.id)
        self.message: Final = message

    @property
    def text(self) -> str:
        return self.message.text or ''

    async def notify(self, text: str):
        await self.message.reply(text, parse_mode=ParseMode.MARKDOWN)

    async def handle(self):
        if not self.text:
            return

        parts = self.text.split()

        if self.skipped(self.message.chat):
            return
        if self.unknown(self.message.chat):
            raise UserException(f'Unknown chat `{self.message.chat.id}`')

        match parts[0]:
            case '/cancel':
                return await self.handle_cancel()

            # auth
            case '/accounts':
                return await self.handle_accounts()
            case '/login':
                return await self.handle_login()
            case '/logout':
                return await self.handle_logout()
            case '/forward':
                return await self.handle_forward()

            # import
            case '/import':
                return await self.handle_import()

            # unknown
            case str(command) if command.startswith('/'):
                return await self.notify('Unknown command')

        if not self.user.idle:
            return await self.handle_state()

        match parts:
            case [url, *pick]:
                return await self.handle_media(url, pick)

    async def handle_cancel(self):
        if self.user.idle:
            await self.notify('Nothing to cancel')
            return

        if isinstance(self.user.state, Importing):
            await self.ctx.cache.discard(self.user.state.rid)

        self.user.state = None
        self.user.save()
        await self.bot.send_message(self.message.chat.id, 'Operation cancelled')

    async def handle_accounts(self):
        accounts = await self.accounts()

        if not accounts:
            await self.notify('No accounts')
            return

        text = 'Accounts:\n'
        for account in accounts:
            text += f'- {C.platforms[account.platform]}: {account.handle}\n'

        await self.notify(text)

    async def handle_login(self):
        self.user.state = AskingLoginPlatform()
        self.user.save()

        buttons = [
            InlineKeyboardButton(C.platforms[platform], callback_data=f'login:{platform}')  #
            for platform in C.platforms
        ]
        await self.message.reply(
            'Which platform?',
            reply_markup=InlineKeyboardMarkup([buttons]),
        )

    async def handle_logout(self):
        accounts = await self.accounts()

        if not accounts:
            await self.notify('Nothing to log out of')
            return

        buttons = [
            InlineKeyboardButton(
                f'{C.platforms[account.platform]}: {account.handle}',
                callback_data=f'logout:{account.platform}:{account.identifier}',
            )
            for account in accounts
        ]

        await self.message.reply(
            'Which account?',
            reply_markup=InlineKeyboardMarkup([[button] for button in buttons]),
        )

    async def handle_forward(self):
        buttons = [
            KeyboardButton(
                text='Choose a Channel',
                request_chat=KeyboardButtonRequestChat(
                    request_id=1,
                    chat_is_channel=True,
                    bot_is_member=True,
                    user_administrator_rights=ChatPrivileges(can_post_messages=True),
                    bot_administrator_rights=ChatPrivileges(can_post_messages=True),
                ),
            ),
            KeyboardButton(
                text='Choose a Group',
                request_chat=KeyboardButtonRequestChat(
                    request_id=2,
                    chat_is_channel=False,
                    bot_is_member=True,
                    user_administrator_rights=ChatPrivileges(can_post_messages=True),
                    bot_administrator_rights=ChatPrivileges(can_post_messages=True),
                ),
            ),
        ]

        await self.message.reply(
            text='Please select a group or channel:',
            reply_markup=ReplyKeyboardMarkup([[*buttons]], resize_keyboard=True),
        )

    async def handle_import(self):
        await self.twitter.authenticate()

        if isinstance(self.user.state, Importing):
            await self.ctx.cache.discard(self.user.state.rid)

        self.user.state = AskingImportAccount()
        self.user.save()

        handles = await self.twitter.handles()
        buttons = [
            InlineKeyboardButton(handle, callback_data=f'import:account:{handle}')  #
            for handle in handles
        ]

        await self.message.reply(
            'Which account to import bookmarks from?',
            reply_markup=InlineKeyboardMarkup([[button] for button in buttons]),
        )

    async def handle_state(self):
        match self.user.state:
            # login
            case AskingLoginPlatform():
                await self.notify('Pick a platform with the buttons above, or /cancel')

            case AskingLoginHandle() as state:
                try:
                    await self.handle_login_handle(state)
                finally:
                    await self.drop_message()

            case AskingLoginSecret() as state:
                try:
                    await self.handle_login_secret(state)
                finally:
                    await self.drop_message()

            # logout
            case AskingLogoutAccount():
                await self.notify('Pick an account with the buttons above, or /cancel')

            # import
            case AskingImportAccount():
                await self.notify('Pick an account with the buttons above, or /cancel')

            case Importing():
                await self.notify('Import is in progress. Use the buttons, or /cancel')

    async def handle_login_handle(self, state: AskingLoginHandle):
        if state.platform not in C.platforms:
            raise StateException('/login')

        self.user.state = AskingLoginSecret(platform=state.platform, handle=self.text.strip())
        self.user.save()

        match state.platform:
            case 'twitter':
                message = (
                    'Send your Twitter cookies, like `auth_token=...; ct0=...`\n'
                    'You can obtain it with [unjar](https://github.com/vladkens/unjar)\n'
                    'Example: `unjar -b brave -f header x.com`'
                )
            case 'bsky':
                message = 'Send your Bluesky password'
            case _:
                raise StateException('/login')

        await self.bot.send_message(self.message.chat.id, message)

    async def handle_login_secret(self, state: AskingLoginSecret):
        secret = self.text.strip()

        match state.platform:
            case 'twitter':
                await self.twitter.login(state.handle, cookies=secret)

            case 'bsky':
                profile = await self.bsky.login(state.handle, secret)
                self.user.bsky[profile.did] = BskyCredentials(
                    handle=state.handle,
                    password=secret,
                    session=self.bsky.export_session_string(),
                )

            case _:
                raise StateException('/login')

        self.user.state = None
        self.user.save()

        await self.bot.send_message(
            self.message.chat.id,
            f'Logged in to {C.platforms[state.platform]} as {state.handle}',
        )

    async def handle_media(self, url: str, pick: Sequence[str] = ()):
        post = await self.get_post(url)
        media = await self.get_media(post)

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
                raise UserException('Invalid picking expression. Example: 1 3-4')

        count = len(media)
        if subset:
            media = [medium for i, medium in enumerate(media) if i + 1 in subset]
            if not media:
                raise UserException(f'None of the {count} media is picked')

        await self.send_album(self.message.chat, post, media, self.markup_single())

    async def drop_message(self):
        """
        Delete the message carrying a secret, best effort.
        """

        try:
            await self.message.delete()
        except RPCError:
            logger.warning('Could not delete message {} in {}', self.message.id, self.message.chat.id)

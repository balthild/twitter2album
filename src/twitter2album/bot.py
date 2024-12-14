import os
import traceback
from typing import Self
from urllib.parse import urlparse
from aiohttp import ClientSession
from loguru import logger
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import CallbackQuery, Chat, Message, InputMedia, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageEntityType

from twitter2album.config import Config
from twitter2album.error import UserException
from twitter2album.twitter import TweetEx, TwitterClient
from twitter2album.bsky import BskyClient, BskyPostEx


async def start():
    logger.info('Starting bot')
    async with Context():
        logger.info('Handling incoming messages (Ctrl+C to stop)')
        await idle()
        logger.info('Stopping bot')


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

        self.bot.add_handler(MessageHandler(TextHandler(self).forward, filters.text))
        self.bot.add_handler(CallbackQueryHandler(ButtonHandler(self).forward))

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


class ContextualHandler:
    def __init__(self, ctx: Context):
        self.config = ctx.config
        self.twitter = ctx.twitter
        self.bsky = ctx.bsky
        self.http = ctx.http
        self.bot = ctx.bot

    async def forward(self, bot: Client, *args):
        try:
            await self.assign(*args)
            await self.handle()
        except UserException as e:
            await self.notify(str(e))
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()
            await self.notify('Internal Error')

    async def assign(self, *args): ...
    async def notify(self, text: str): ...
    async def handle(self): ...

    async def get_post(self, url: str):
        parsed = urlparse(url)
        if parsed.netloc in self.config.domains.twitter:
            return await self.twitter.get_tweet_ex(parsed)
        elif parsed.netloc in self.config.domains.bsky:
            return await self.bsky.get_post_ex(parsed)
        else:
            raise UserException('Unrecognized URL')

    async def get_album(self, post: BskyPostEx | TweetEx):
        album = []
        for photo in post.photos():
            album.append(InputMediaPhoto(photo))
        for video in post.videos():
            album.append(InputMediaVideo(video))
        for gif in post.gifs():
            album.append(InputMediaVideo(gif, disable_content_type_detection=True))

        return album

    async def send_album(self, chat: Chat, post: BskyPostEx | TweetEx, album: list[InputMedia]):
        url = post.url()
        content = post.render()

        source = f'<a href="{url}">source</a>'
        sep = '\n' if '\n' in content else ' '
        album[0].caption = f'{content}{sep}{source}'.strip()

        [message] = await self.bot.send_media_group(chat.id, album)

        await message.edit_reply_markup(self.get_action_buttons())

    def get_action_buttons(self, silent: bool = False):
        actions = [
            'Caption' if silent else 'Silent',
            'Pick', 'Forward'
        ]

        return InlineKeyboardMarkup([[
            InlineKeyboardButton(action, callback_data=action)
            for action in actions
        ]])


class TextHandler(ContextualHandler):
    async def assign(self, message: Message):
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
            case [url]:
                await self.handle_resource(url)

    async def handle_chatid(self):
        await self.message.reply(f'Chat ID: {self.message.chat.id}')

    async def handle_relogin(self):
        success, failed = await self.twitter.relogin()
        await self.message.reply(f'Success: {success}\nFailed: {failed}')

    async def handle_resource(self, url: str, subset: list[int] = []):
        post = await self.get_post(url)
        album = await self.get_album(post)
        if subset:
            album = [medium for i, medium in enumerate(album) if i+1 in subset]

        await self.send_album(self.message.chat, post, album)


class ButtonHandler(ContextualHandler):
    async def assign(self, query: CallbackQuery):
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
            case 'Pick':
                await self.handle_pick()
            case 'Forward':
                await self.handle_forward()
            case _:
                await self.query.answer('Unrecognized Button')

    async def handle_silent(self):
        url = self.get_source_url()
        source = f'<a href="{url}">source</a>'
        buttons = self.get_action_buttons(silent=True)
        await self.message.edit_caption(source, reply_markup=buttons)

    async def handle_caption(self):
        url = self.get_source_url()
        post = await self.get_post(url)

        url = post.url()
        source = f'<a href="{url}">source</a>'
        content = post.render()
        sep = '\n' if '\n' in content else ' '

        caption = f'{content}{sep}{source}'.strip()
        buttons = self.get_action_buttons()

        await self.message.edit_caption(caption, reply_markup=buttons)

    async def handle_pick(self):
        await self.query.answer('TODO: pick')

    async def handle_forward(self):
        await self.message.forward(self.config.telegram.forward_to)
        await self.query.answer('Forwarded')

    def get_source_url(self):
        for entity in reversed(self.message.caption_entities):
            if entity.type == MessageEntityType.TEXT_LINK:
                return entity.url
        raise UserException('Cannot find post source. Please send the source URL again')

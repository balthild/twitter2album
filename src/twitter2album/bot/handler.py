import traceback
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


class ContextualHandler(Handler):
    def __init__(self, ctx: Context, filters: Filter = None):
        super().__init__(self.forward, filters)
        self.config = ctx.config
        self.twitter = ctx.twitter
        self.bsky = ctx.bsky
        self.http = ctx.http
        self.bot = ctx.bot

    async def forward(self, bot: Client, *args):
        try:
            await self.args(*args)
            await self.handle()
        except UserException as e:
            await self.notify(str(e))
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()
            await self.notify('Internal Error')

    async def args(self, *args, **kwargs): ...
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
            album.append(InputMediaVideo(
                gif, disable_content_type_detection=True))

        return album

    async def send_album(self, chat: Chat, post: BskyPostEx | TweetEx, album: list[InputMedia]):
        url = post.url()
        content = post.render()

        source = f'<a href="{url}">source</a>'
        sep = '\n' if '\n' in content else ' '
        album[0].caption = f'{content}{sep}{source}'.strip()
        album[0].parse_mode = ParseMode.HTML

        [message] = await self.bot.send_media_group(chat.id, album)

        await message.edit_reply_markup(self.get_action_buttons())

    def get_action_buttons(self, old: InlineKeyboardMarkup = None):
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

        return InlineKeyboardMarkup([[
            InlineKeyboardButton(action, callback_data=action)
            for action in actions
        ]])

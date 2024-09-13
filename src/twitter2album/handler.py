import sqlite3
import traceback
from urllib.parse import urlparse
from aiohttp import ClientSession
from twscrape import API, logger
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, InputMedia, InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ChatType

from twitter2album.config import Config
from twitter2album.error import UserException
from twitter2album.tweet import render_content


class Handler(MessageHandler):
    def __init__(self, config: Config, twitter: API, http: ClientSession):
        super().__init__(self.handle, filters.text)
        self.config = config
        self.twitter = twitter
        self.http = http

    async def handle(self, bot: Client, message: Message):
        try:
            inner = _HandlerInner(self, bot, message)
            await inner.handle()
        except UserException as e:
            await message.reply(str(e))
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()
            await message.reply('Internal Error')


class _HandlerInner:
    def __init__(self, handler: Handler, bot: Client, message: Message):
        self.config = handler.config
        self.twitter = handler.twitter
        self.http = handler.http
        self.bot = bot
        self.message = message

    async def handle(self):
        if self.message.chat.id not in self.config.telegram.chat_whitelist:
            self.handle_chatid()
            return

        match self.message.text.split():
            case ['/chatid']:
                await self.handle_chatid()
            case ['/relogin']:
                await self.handle_relogin()
            case ['/notext']:
                await self.handle_notext()
            case ['/notext', url]:
                await self.handle_tweet(url, True)
            case [url, *_]:
                await self.handle_tweet(url)

    async def handle_chatid(self):
        await self.message.reply(f'Chat ID: {self.message.chat.id}')

    async def handle_relogin(self):
        await self.twitter.pool.delete_inactive()
        await self.twitter.pool.add_account(self.config.twitter.username, self.config.twitter.password, '', '')

        result = await self.twitter.pool.login_all()
        success, failed = result['success'], result['failed']

        await self.message.reply(f'Success: {success}\nFailed: {failed}')

    async def handle_notext(self):
        return
        settings = sqlite3.connect('settings.db')
        settings.execute('')
        pass

    async def handle_tweet(self, twurl: str, notext: bool | None = None):
        domains = [
            'twitter.com',
            'x.com',
            'fixvx.com',
            'fixupx.com',
            'vxtwitter.com',
            'fxtwitter.com',
        ]

        urlobj = urlparse(twurl)
        if urlobj.netloc not in domains:
            raise UserException('Invalid tweet URL')

        match urlobj.path.split('/'):
            case ['', _, 'status', twid, *_]:
                twid = int(twid)
            case _:
                raise UserException('Invalid tweet URL')

        tweet = await self.twitter.tweet_details(twid)
        if tweet is None:
            raise UserException(f'Tweet {twid} not found')

        album = []

        for photo in tweet.media.photos:
            album.append(InputMediaPhoto(photo.url))

        for video in tweet.media.videos:
            candidate = None
            for variant in video.variants:
                if variant.contentType != 'video/mp4':
                    continue
                if candidate is None or variant.bitrate > candidate.bitrate:
                    candidate = variant

            if candidate is None:
                formats = [x.contentType for x in video.variants]
                formats = ', '.join(set(formats))
                raise UserException(f'Unrecognized video formats: {formats}')

            album.append(InputMediaVideo(candidate.url))

        for gif in tweet.media.animated:
            album.append(InputMediaVideo(gif.videoUrl))

        if not album:
            raise UserException(f'Tweet {twid} contains no media')

        album[0].caption = render_content(tweet, notext)

        if tweet.media.animated:
            # GIF in album requires uploading from local with `nosound_video` flag
            # So I send the album via Bot API
            await self.bot_api_reply_media_group(album)
        else:
            await self.message.reply_media_group(album)

    async def bot_api_reply_media_group(self, album: list[InputMedia]):
        token = self.config.telegram.bot_token
        url = f'https://api.telegram.org/bot{token}/sendMediaGroup'

        body = {
            "chat_id": self.message.chat.id,
            "media": [],
        }

        for item in album:
            match item:
                case InputMediaPhoto(media=media, caption=caption):
                    type = 'photo'
                case InputMediaVideo(media=media, caption=caption):
                    type = 'video'
                case _:
                    raise Exception('Unreachable')

            body['media'].append({
                'type': type,
                'media': media,
                'caption': caption,
                'parse_mode': 'HTML'
            })

        if self.message.chat.type != ChatType.PRIVATE:
            body["reply_parameters"] = {"message_id": self.message.id}

        async with self.http.post(url, json=body) as response:
            if response.status != 200:
                text = await response.text()
                text = f'Bot API error: {response.status}\n{text}'.strip()
                raise Exception(text)

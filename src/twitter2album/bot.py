import os
import sqlite3
import traceback
from typing import Self
from urllib.parse import urlparse, ParseResult as URL
from aiohttp import ClientSession
from atproto_client.models.app.bsky.embed.images import View as ImagesView
from atproto_client.models.app.bsky.embed.video import View as VideoView
from loguru import logger
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, InputMedia, InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ChatType

from twitter2album.config import Config
from twitter2album.error import UserException
from twitter2album.twitter import TwitterClient, render_tweet
from twitter2album.bsky import BskyClient, render_bsky_post
from twitter2album.utils import dbg


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
        self.bot.add_handler(MessageHandler(self.handle, filters.text))

    async def handle(self, bot: Client, message: Message):
        try:
            handler = Handler(self, bot, message)
            await handler.handle()
        except UserException as e:
            await message.reply(str(e))
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()
            await message.reply('Internal Error')

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


class Handler:
    def __init__(self, ctx: Context, bot: Client, message: Message):
        self.config = ctx.config
        self.twitter = ctx.twitter
        self.bsky = ctx.bsky
        self.http = ctx.http

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
                await self.handle_resource(url, True)
            case [url, *_]:
                await self.handle_resource(url)

    async def handle_chatid(self):
        await self.message.reply(f'Chat ID: {self.message.chat.id}')

    async def handle_relogin(self):
        success, failed = await self.twitter.relogin()
        await self.message.reply(f'Success: {success}\nFailed: {failed}')

    async def handle_notext(self):
        return
        settings = sqlite3.connect('settings.db')
        settings.execute('')
        pass

    async def handle_resource(self, url: str, notext: bool = False):
        parsed = urlparse(url)

        if parsed.netloc in self.config.domains.twitter:
            return await self.handle_tweet(parsed, notext)
        elif parsed.netloc in self.config.domains.bsky:
            return await self.handle_bsky(parsed, notext)

        raise UserException('Unrecognized URL')

    async def handle_tweet(self, url: URL, notext: bool):
        match url.path.split('/'):
            case ['', _, 'status', twid, *_]:
                twid = int(twid)
            case _:
                raise UserException('Invalid tweet URL')

        tweet = await self.twitter.tweet_details(twid)
        if tweet is None:
            raise UserException(f'Tweet `{twid}` not found')

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
            raise UserException(f'Tweet `{twid}` contains no media')

        album[0].caption = render_tweet(tweet, notext)

        if tweet.media.animated:
            # GIF in album requires uploading from local with `nosound_video` flag
            # So I send the album via Bot API
            await self.bot_api_reply_media_group(album)
        else:
            await self.message.reply_media_group(album)

    async def handle_bsky(self, url: URL, notext: bool):
        match url.path.split('/'):
            case ['', 'profile', author, 'post', rkey, *_]:
                uri = f'at://{author}/app.bsky.feed.post/{rkey}'
            case _:
                raise UserException('Invalid bsky post URL')

        try:
            response = await self.bsky.get_post_thread(uri, depth=0, parent_height=0)
        except:
            raise UserException(f'Post `{rkey}` not found')

        album = []

        match response.thread.post.embed:
            case ImagesView(images=images):
                for image in images:
                    album.append(InputMediaPhoto(image.fullsize))

            case VideoView():
                # TODO
                dbg(response.thread.post.embed)
                pass

        if not album:
            raise UserException(f'Post `{rkey}` contains no media')

        album[0].caption = render_bsky_post(response.thread.post, notext)

        await self.bot_api_reply_media_group(album)

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

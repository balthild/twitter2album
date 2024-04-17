from urllib.parse import urlparse
from twscrape import API, Media
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo

from twitter2album.config import Config
from twitter2album.tweet import render_content


class Handler(MessageHandler):
    def __init__(self, config: Config, twitter: API):
        super().__init__(self.handle, filters.text)
        self.config = config
        self.twitter = twitter

    async def handle(self, bot: Client, message: Message):
        try:
            inner = _HandlerInner(self.config, self.twitter, bot, message)
            await inner.handle()
        except Exception as e:
            await message.reply(str(e))


class _HandlerInner:
    def __init__(self, config: Config, twitter: API, bot: Client, message: Message):
        self.config = config
        self.twitter = twitter
        self.bot = bot
        self.message = message

    async def handle(self):
        if self.message.chat.id not in self.config.telegram.chat_whitelist:
            await self.message.reply(f'Chat ID: {self.message.chat.id}')
            return

        match self.message.text.split():
            case ['/notext']:
                await self.handle_notext()
            case ['/notext', url]:
                await self.handle_tweet(url, True)
            case [url, *_]:
                await self.handle_tweet(url)

    async def handle_notext(self):
        pass

    async def handle_tweet(self, twurl: str, notext: bool | None = None):
        domains = [
            'twitter.com',
            'x.com',
            'vxtwitter.com',
            'fxtwitter.com',
        ]

        urlobj = urlparse(twurl)
        if urlobj.netloc not in domains:
            raise Exception('Invalid tweet URL')

        match urlobj.path.split('/'):
            case ['', _, 'status', twid, *_]:
                twid = int(twid)
            case _:
                raise Exception('Invalid tweet URL')

        tweet = await self.twitter.tweet_details(twid)
        if tweet is None:
            raise Exception(f'Tweet {twid} not found')

        match tweet.media:
            case Media(photos=[], videos=[], animated=[]):
                raise Exception(f'Tweet {twid} contains no media')

        group = []

        for photo in tweet.media.photos:
            caption = '' if group else render_content(tweet, notext)
            group.append(InputMediaPhoto(photo.url, caption=caption))

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
                raise Exception(f'Unrecognized video formats: {formats}')

            caption = '' if group else render_content(tweet, notext)
            group.append(InputMediaVideo(candidate.url, caption=caption))

        for gif in tweet.media.animated:
            caption = '' if group else render_content(tweet, notext)
            group.append(InputMediaVideo(gif.videoUrl, caption=caption))

        await self.message.reply_media_group(group)

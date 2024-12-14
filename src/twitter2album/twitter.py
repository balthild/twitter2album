import re
from typing import Self
from loguru import logger
from twscrape import API, Tweet
from urllib.parse import ParseResult as URL

from twitter2album.config import Config
from twitter2album.error import UserException


class TwitterClient(API):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config.twitter

    async def authenticate(self):
        account = await self.pool.get_account(self.config.username)
        if account:
            logger.info('Signing in Twitter with saved session')
        else:
            logger.info('Signing in Twitter with password')
            await self.pool.add_account(self.config.username, self.config.password, '', '')

        await self.pool.login_all()

    async def relogin(self):
        await self.pool.delete_inactive()
        await self.pool.add_account(self.config.username, self.config.password, '', '')

        result = await self.pool.login_all()

        return (result['success'], result['failed'])

    async def get_tweet_ex(self, url: URL):
        match url.path.split('/'):
            case ['', _, 'status', twid, *_]:
                twid = int(twid)
            case _:
                raise UserException('Invalid tweet URL')

        tweet = await self.tweet_details(twid)
        if tweet is None:
            raise UserException(f'Tweet `{twid}` not found')

        if not tweet.media.photos + tweet.media.videos + tweet.media.animated:
            raise UserException(f'Tweet `{twid}` contains no media')

        return TweetEx(tweet)

    async def __aenter__(self) -> Self:
        await self.authenticate()
        return self

    async def __aexit__(self, *args):
        pass


class TweetEx:
    def __init__(self, inner: Tweet) -> None:
        self.inner = inner

    def url(self):
        url = self.inner.url
        return url.replace('https://x.com/', 'https://twitter.com/')

    def render(self):
        content = self.inner.rawContent

        for link in self.inner.links:
            anchor = f'<a href="{link.url}">{link.text}</a>'
            content = content.replace(link.tcourl, anchor)

        content = re.sub(r'https://t\.co/\w+', '', content).strip()

        return content

    def photos(self):
        return [photo.url for photo in self.inner.media.photos]

    def videos(self):
        videos = []

        for video in self.inner.media.videos:
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

            videos.append(candidate.url)

        return videos

    def gifs(self):
        return [gif.videoUrl for gif in self.inner.media.animated]

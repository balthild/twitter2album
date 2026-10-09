from __future__ import annotations

import re
from typing import Final
from urllib.parse import ParseResult as URL
from urllib.parse import urlparse

from loguru import logger
from twscrape import API, Tweet

from twitter2album.const import C
from twitter2album.error import UserException

from .post import AbstractPost


class TwitterClient(API):
    """A twscrape client whose account pool belongs to a single Telegram user.

    twscrape picks whichever account is free from its pool and offers no way to pin
    a request to one account, so isolating users means giving each their own pool.
    The pool is also this user's only account store; nothing is kept in the database.
    """

    def __init__(self, user_id: int):
        path = C.dirs.twscrape / f'{user_id}'
        path.mkdir(parents=True, exist_ok=True)
        super().__init__(pool=str(path / 'pool.db'))

        self.user_id: Final = user_id
        self.authenticated = False

    async def authenticate(self):
        if self.authenticated:
            return

        if not await self.handles():
            raise UserException('Twitter is not logged in. Use /login to add an account')

        self.authenticated = True

    async def login(self, handle: str, *, cookies: str):
        logger.info('Adding Twitter account {}', handle)
        try:
            await self.pool.add_account_cookies(handle, cookies)
        except ValueError as e:
            raise UserException(f'Invalid Twitter cookies: {e}')

    async def logout(self, handle: str):
        logger.info('Removing Twitter account {}', handle)
        await self.pool.delete_accounts(handle)

    async def handles(self) -> list[str]:
        return [account.username for account in await self.pool.get_all()]

    async def get_tweet_ex(self, url: URL) -> TweetEx:
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


class TweetEx(AbstractPost):
    def __init__(self, inner: Tweet) -> None:
        self.inner: Final = inner

    def url(self):
        parsed = urlparse(self.inner.url)
        parsed = parsed._replace(netloc='twitter.com')
        return parsed.geturl()

    def render(self):
        content = self.inner.rawContent

        for link in self.inner.links:
            if link.tcourl:
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
                formats = [f'`{x.contentType}`' for x in video.variants]
                formats = ', '.join(set(formats))
                raise UserException(f'Unrecognized video formats: {formats}')

            videos.append(candidate.url)

        return videos

    def gifs(self):
        return [gif.videoUrl for gif in self.inner.media.animated]

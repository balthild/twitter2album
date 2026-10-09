from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from typing import Final
from urllib.parse import ParseResult as URL
from urllib.parse import urlparse

from loguru import logger
from twscrape import API, AccountsPool, NoAccountError, Tweet
from twscrape.api import GQL_FEATURES, GQL_URL
from twscrape.http import Response
from twscrape.queue_client import QueueClient, XClIdGenStore

from twitter2album.const import C
from twitter2album.error import UserException

from .post import AbstractPost

# twscrape has no bookmark write API, so removal goes through this raw GraphQL
# operation. X rotates operation ids periodically; re-capture it from the browser
# when removal starts failing. Deliberately not in twscrape's own op-id block,
# which a generator script rewrites wholesale.
OP_DELETE_BOOKMARK = 'Wlmlj2-xzyS1GN3a6cj-mQ/DeleteBookmark'


def parse_tweet_id(url: str) -> int:
    match urlparse(url).path.split('/'):
        case ['', _, 'status', twid, *_]:
            return int(twid)
        case _:
            raise UserException('Invalid tweet URL')


class TwitterClient(API):
    """
    A twscrape client whose account pool belongs to a single Telegram user.

    twscrape picks whichever account is free from its pool and offers no way to pin
    a request to one account, so isolating users means giving each their own pool.
    The pool is also this user's only account store; nothing is kept in the database.
    """

    def __init__(self, user_id: int):
        path = C.dirs.twscrape / str(user_id)
        path.mkdir(parents=True, exist_ok=True)
        super().__init__(pool=str(path / 'pool.db'))

        self.user_id: Final = user_id
        self.path: Final = path
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
        twid = parse_tweet_id(url.geturl())

        tweet = await self.tweet_details(twid)
        if tweet is None:
            raise UserException(f'Tweet `{twid}` not found')

        if not tweet.media.photos + tweet.media.videos + tweet.media.animated:
            raise UserException(f'Tweet `{twid}` contains no media')

        return TweetEx(tweet)

    async def bookmarks_of(self, handle: str, limit: int = -1) -> AsyncGenerator[Tweet, None]:
        api = await self._isolated(handle)

        try:
            async for tweet in api.bookmarks(limit=limit):
                yield tweet
        except NoAccountError as e:
            raise UserException(f'Twitter rate limit reached for `{handle}`. Try again later') from e

    async def remove_bookmark_of(self, handle: str, tweet_id: int):
        api = await self._isolated(handle)

        try:
            response = await self._post_gql(api, OP_DELETE_BOOKMARK, {'tweet_id': str(tweet_id)})
        except NoAccountError as e:
            raise UserException(f'Twitter rate limit reached for `{handle}`. Try again later') from e

        # A response without `errors` is the only success signal to rely on: the shape
        # of a successful mutation body is not something twscrape documents.
        errors = response.json().get('errors') or []
        if errors:
            detail = '; '.join(f'({err.get("code", -1)}) {err.get("message", "")}' for err in errors)
            raise UserException(f'Could not remove bookmark `{tweet_id}`: {detail}')

    async def _post_gql(self, api: API, op: str, variables: dict) -> Response:
        """
        Send a GraphQL mutation and return the raw response.

        twscrape only implements GET, and X rejects a mutation sent that way with
        "GET requests only allow query operations". So the POST is assembled here out
        of the parts twscrape itself uses: the pool lends an account, and the client
        transaction id is generated for the method and path just as for a GET. The
        body shape (variables + queryId + features) is what X's web client sends.
        """

        qid, _, queue = op.partition('/')
        url = f'{GQL_URL}/{op}'
        body = {'variables': variables, 'queryId': qid, 'features': GQL_FEATURES}

        async with QueueClient(api.pool, queue, api.debug, proxy=api.proxy) as client:
            ctx = client.ctx
            if ctx is None:
                raise UserException('Twitter is not available right now. Try again later')

            transaction = await XClIdGenStore.get(ctx.acc.username, proxy=ctx.proxy, cookies=ctx.acc.cookies)
            headers = {'x-client-transaction-id': transaction.calc('POST', urlparse(url).path)}

            return await ctx.clt.post(url, json=body, headers=headers)

    async def _isolated(self, handle: str) -> API:
        """
        Return an API whose account pool holds only `handle`.

        twscrape picks whichever account in a pool is free for a queue, and bookmarks
        belong to an individual account, so giving a call its own pool is the only way
        to read the bookmarks of the account the user picked.
        """

        await self.authenticate()

        try:
            account = await self.pool.get(handle)
        except ValueError as e:
            raise UserException(f'Twitter account `{handle}` is not logged in') from e

        if not account.active or not account.has_session:
            raise UserException(f'Twitter account `{handle}` is not usable. Use /login to refresh it')

        path = self.path / 'isolated'
        path.mkdir(parents=True, exist_ok=True)

        # The flags belong on the pool: `API(pool, raise_when_no_account=...)` ignores
        # them when handed an existing pool, and the default is to block *forever* once
        # every account is rate limited. These make the pool give up instead, so the
        # caller is told rather than left hanging.
        pool = AccountsPool(
            db_file=str(path / f'{handle}.db'),
            raise_when_no_account=True,
            wait_timeout=0,
        )

        # Keep the lock this pool already recorded rather than the main pool's: a rate
        # limit is per account and per queue, and clearing it would make every retry
        # hammer an account X has just refused.
        try:
            account.locks = (await pool.get(handle)).locks
        except ValueError:
            account.locks = {}

        await pool.save(account)

        return API(pool)


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

import re
from typing import Self
from loguru import logger
from twscrape import API, Tweet

from twitter2album.config import Config


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

    async def __aenter__(self) -> Self:
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def render_tweet(tweet: Tweet, notext: bool) -> str:
    source = f'<a href="{tweet.url}">source</a>'
    if notext:
        return source

    content = tweet.rawContent

    for link in tweet.links:
        anchor = f'<a href="{link.url}">{link.text}</a>'
        content = content.replace(link.tcourl, anchor)

    content = re.sub(r'https://t\.co/\w+', '', content).strip()

    sep = '\n' if '\n' in content else ' '
    return f'{content}{sep}{source}'.strip()

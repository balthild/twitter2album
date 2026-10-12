from loguru import logger
from pyrogram import idle

from twitter2album.bot.context import Context
from twitter2album.config import Config


async def start(config: Config):
    async with Context(config):
        logger.info('Handling incoming messages (Ctrl+C to stop)')
        await idle()


__all__ = ['start']

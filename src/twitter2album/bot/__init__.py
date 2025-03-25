from loguru import logger
from pyrogram import idle

from twitter2album.bot.context import Context


async def start():
    logger.info('Starting bot')
    async with Context():
        logger.info('Handling incoming messages (Ctrl+C to stop)')
        await idle()
        logger.info('Stopping bot')

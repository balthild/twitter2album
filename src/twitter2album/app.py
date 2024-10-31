import os
from loguru import logger
from pyrogram import Client, idle

from twitter2album.config import Config
from twitter2album.handler import Handler


async def start():
    config = Config.load()

    bot = Client(
        name=config.telegram.bot_token.split(':')[0],
        bot_token=config.telegram.bot_token,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        workdir=os.getcwd(),
    )

    handler = Handler(config)
    bot.add_handler(handler)

    logger.info('Starting bot')
    async with bot, handler:
        logger.info('Handling incoming messages (Ctrl+C to stop)')
        await idle()
        logger.info('Stopping bot')

import os
from aiohttp import ClientSession
from twscrape import API, logger
from pyrogram import Client, idle

from twitter2album.config import Config
from twitter2album.handler import Handler


async def start():
    config = Config.load()

    twitter = API()
    await twitter.pool.add_account(config.twitter.username, config.twitter.password, '', '')
    await twitter.pool.login_all()

    http = ClientSession()

    bot = Client(
        name=config.telegram.bot_token.split(':')[0],
        bot_token=config.telegram.bot_token,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        workdir=os.getcwd(),
    )
    bot.add_handler(Handler(config, twitter, http))

    logger.info('Starting bot')
    async with bot:
        logger.info('Handling incoming messages (Ctrl+C to stop)')
        await idle()
        logger.info('Stopping bot')
        await http.close()

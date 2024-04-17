from twscrape import API, logger
from pyrogram import Client, idle

from twitter2album.config import Config
from twitter2album.handler import Handler

async def start():
    config = Config.load()

    twitter = API()
    await twitter.pool.add_account(config.twitter.username, config.twitter.password, '', '')
    await twitter.pool.login_all()

    bot = Client(
        name='twitter2album',
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        bot_token=config.telegram.bot_token,
    )
    bot.add_handler(Handler(config, twitter))

    await bot.start()
    logger.info('Bot started')

    await idle()
    await bot.stop()
    logger.info('Bot stopped')

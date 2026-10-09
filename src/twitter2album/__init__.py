import os

import uvloop

from .config import Config


def main():
    config = Config.load()

    os.environ['TWS_HTTP_BACKEND'] = 'curl'
    os.environ['LOGURU_LEVEL'] = config.log.level

    from . import bot

    uvloop.run(bot.start(config))

import inspect
import logging
import os
import sys

import twscrape.logger
import uvloop
from loguru import logger

from .config import Config


def main():
    config = Config.load()

    os.environ["TWS_HTTP_BACKEND"] = "curl"
    os.environ["LOGURU_LEVEL"] = config.log.level

    twscrape.logger.set_log_level = lambda _: ...  # type: ignore
    twscrape.logger._LOG_LEVEL = config.log.level

    logger.remove()
    logger.add(sys.stderr, level=config.log.level)

    logging.basicConfig(handlers=[LoguruHandler()], level=0, force=True)

    from . import bot

    uvloop.run(bot.start(config))


class LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        depth, frame = 0, inspect.currentframe()
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

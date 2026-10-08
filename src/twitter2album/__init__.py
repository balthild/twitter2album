import os

import uvloop

import twitter2album.bot


def main():
    os.environ.setdefault('TWS_HTTP_BACKEND', 'curl')
    uvloop.run(twitter2album.bot.start())

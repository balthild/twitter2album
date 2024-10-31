import uvloop
import twitter2album.bot


def main():
    uvloop.run(twitter2album.bot.start())

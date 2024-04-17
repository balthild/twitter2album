import uvloop
import twitter2album.app


def main():
    uvloop.run(twitter2album.app.start())

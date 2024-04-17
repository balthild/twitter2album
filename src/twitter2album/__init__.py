import asyncio
import uvloop
import twitter2album.app

def main():
    uvloop.install()
    asyncio.run(twitter2album.app.start())

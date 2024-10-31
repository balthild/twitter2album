from typing import Self
from atproto import Session, SessionEvent, AsyncClient
from atproto_client.models.app.bsky.feed.defs import PostView
from atproto_client.models.app.bsky.richtext.facet import Link
from loguru import logger

from twitter2album.config import Config


class BskyClient(AsyncClient):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config.bsky

    async def authenticate(self):
        self.on_session_change(_persist_session)

        session = _get_session()
        if session:
            logger.info('Signing in Bluesky with saved session')
            return await self.login(session_string=session)
        else:
            logger.info('Signing in Bluesky with password')
            return await self.login(self.config.username, self.config.password)

    async def __aenter__(self) -> Self:
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def render_bsky_post(post: PostView, notext: bool) -> str:
    [did, _, rkey] = post.uri.removeprefix('at://').split('/')
    source = f'<a href="https://bsky.app/profile/{did}/post/{rkey}">source</a>'
    if notext:
        return source

    data = bytes(post.record.text, 'utf-8')

    links: list[tuple[int, int, str]] = []
    for facet in post.record.facets or []:
        for feature in facet.features:
            match feature:
                case Link(uri=uri):
                    link = (facet.index.byte_start, facet.index.byte_end, uri)
                    links.append(link)
                    break

    links.sort(key=lambda x: x[0])

    segments = []
    index = 0
    for link in links:
        start, end, url = link

        segments.append(data[index:start].decode())
        index = start

        segments.append(f'<a href="{url}">')

        segments.append(data[index:end].decode())
        index = end

        segments.append('</a>')

    segments.append(data[index:].decode())

    content = ''.join(segments)

    sep = '\n' if '\n' in content else ' '
    return f'{content}{sep}{source}'.strip()


def _get_session() -> str:
    try:
        with open('bsky.session') as f:
            return f.read()
    except FileNotFoundError:
        return None


async def _persist_session(event: SessionEvent, session: Session):
    if (event in (SessionEvent.CREATE, SessionEvent.REFRESH)):
        with open('bsky.session', 'w') as f:
            f.write(session.export())

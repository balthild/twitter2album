from typing import Self
from urllib.parse import ParseResult as URL

from atproto import AsyncClient, Session, SessionEvent
from atproto_client.models.app.bsky.embed.images import View as ImagesView
from atproto_client.models.app.bsky.embed.video import View as VideoView
from atproto_client.models.app.bsky.feed.defs import PostView
from atproto_client.models.app.bsky.richtext.facet import Link
from loguru import logger

from twitter2album.config import Config
from twitter2album.error import UserException


class BskyClient(AsyncClient):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config.bsky

    async def authenticate(self):
        self.on_session_change(persist_session)

        session = get_session()
        if session:
            logger.info('Signing in Bluesky with saved session')
            return await self.login(session_string=session)
        else:
            logger.info('Signing in Bluesky with password')
            return await self.login(self.config.username, self.config.password)

    async def get_post_ex(self, url: URL):
        match url.path.split('/'):
            case ['', 'profile', author, 'post', rkey, *_]:
                uri = f'at://{author}/app.bsky.feed.post/{rkey}'
            case _:
                raise UserException('Invalid bsky post URL')

        try:
            response = await self.get_post_thread(uri, depth=0, parent_height=0)
        except Exception:
            raise UserException(f'Post `{rkey}` not found')

        if not response.thread.post.embed:
            raise UserException(f'Post `{rkey}` contains no media')

        return BskyPostEx(response.thread.post)

    async def __aenter__(self) -> Self:
        await self.authenticate()
        return self

    async def __aexit__(self, *args):
        pass


class BskyPostEx:
    def __init__(self, inner: PostView) -> None:
        self.inner = inner

    def url(self) -> str:
        [did, _, rkey] = self.inner.uri.removeprefix('at://').split('/')
        return f'https://bsky.app/profile/{did}/post/{rkey}'

    def render(self) -> str:
        data = bytes(self.inner.record.text, 'utf-8')

        links: list[tuple[int, int, str]] = []
        for facet in self.inner.record.facets or []:
            start = facet.index.byte_start
            end = facet.index.byte_end
            for feature in facet.features:
                match feature:
                    case Link(uri=uri):
                        links.append((start, end, uri))
                        break

        links.sort(key=lambda x: x[0])

        segments = []

        index = 0
        for start, end, url in links:
            segments.append(data[index:start].decode())
            segments.append(f'<a href="{url}">')
            segments.append(data[start:end].decode())
            segments.append('</a>')
            index = end

        segments.append(data[index:].decode())

        return ''.join(segments)

    def photos(self):
        match self.inner.embed:
            case ImagesView(images=images):
                return [image.fullsize for image in images]

        return []

    def videos(self):
        # TODO
        match self.inner.embed:
            case VideoView():
                return []

        return []

    def gifs(self):
        # TODO
        return []


def get_session() -> str:
    try:
        with open('bsky.session') as f:
            return f.read()
    except FileNotFoundError:
        return None


async def persist_session(event: SessionEvent, session: Session):
    if (event in (SessionEvent.CREATE, SessionEvent.REFRESH)):
        with open('bsky.session', 'w') as f:
            f.write(session.export())

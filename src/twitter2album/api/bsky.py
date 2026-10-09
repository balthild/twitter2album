from __future__ import annotations

from typing import Final
from urllib.parse import ParseResult as URL

from atproto import AsyncClient, Session, SessionEvent
from atproto.exceptions import AtProtocolError
from atproto_client.models.app.bsky.actor.defs import ProfileViewDetailed
from atproto_client.models.app.bsky.embed.images import View as ImagesView
from atproto_client.models.app.bsky.embed.video import View as VideoView
from atproto_client.models.app.bsky.feed.defs import PostView, ThreadViewPost
from atproto_client.models.app.bsky.feed.post import Record
from atproto_client.models.app.bsky.richtext.facet import Link
from loguru import logger

from twitter2album.db.user import User
from twitter2album.error import UserException

from .post import AbstractPost


class BskyClient(AsyncClient):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id: Final = user_id
        self.profile: ProfileViewDetailed | None = None

        self.on_session_change(self.persist_session)

    async def authenticate(self):
        if self.profile is not None:
            return

        user = User.resolve(self.user_id)
        if not user.bsky:
            raise UserException('Bluesky is not logged in. Use /login to add an account')

        # Reading a public post needs no particular account, so use the first one.
        did = next(iter(user.bsky))
        credentials = user.bsky[did]

        try:
            logger.info('Signing in Bluesky as {} with saved session', credentials.handle)
            await self.login(session_string=credentials.session)
        except (AtProtocolError, UserException):
            logger.info('Signing in Bluesky as {} with password', credentials.handle)
            await self.login(credentials.handle, credentials.password)

    async def login(self, *args, **kwargs) -> ProfileViewDetailed:
        try:
            kwargs.pop('fetch_bsky_profile', None)
            self.profile = await super().login(*args, **kwargs, fetch_bsky_profile=True)
            assert self.profile is not None
            return self.profile
        except AtProtocolError as e:
            raise UserException(f'Bluesky login failed: {e}')

    async def persist_session(self, event: SessionEvent, session: Session):
        if event not in (SessionEvent.CREATE, SessionEvent.REFRESH):
            return
        if self.profile is None:
            return

        # Re-read rather than keeping a User around: this client outlives a single
        # message, and saving a stale copy would clobber unrelated fields.
        user = User.resolve(self.user_id)
        if self.profile.did not in user.bsky:
            return

        user.bsky[self.profile.did].session = session.export()
        user.save()

    async def get_post_ex(self, url: URL) -> BskyPostEx:
        match url.path.split('/'):
            case ['', 'profile', author, 'post', rkey, *_]:
                uri = f'at://{author}/app.bsky.feed.post/{rkey}'
            case _:
                raise UserException('Invalid bsky post URL')

        try:
            response = await self.get_post_thread(uri, depth=0, parent_height=0)
        except AtProtocolError:
            raise UserException(f'Post `{rkey}` not found')

        match response.thread:
            case ThreadViewPost(post=post) if post.embed:
                return BskyPostEx(post)
            case ThreadViewPost():
                raise UserException(f'Post `{rkey}` contains no media')
            case _ as thread:
                raise UserException(f'Post `{rkey}` has unknown type: {type(thread)}')


class BskyPostEx(AbstractPost):
    def __init__(self, inner: PostView) -> None:
        if not isinstance(inner.record, Record):
            raise UserException('Invalid bsky post')

        self.inner: Final = inner
        self.record: Final = inner.record

    def url(self) -> str:
        [did, _, rkey] = self.inner.uri.removeprefix('at://').split('/')
        return f'https://bsky.app/profile/{did}/post/{rkey}'

    def render(self) -> str:
        data = bytes(self.record.text, 'utf-8')

        links: list[tuple[int, int, str]] = []
        for facet in self.record.facets or []:
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

from dataclasses import field
from typing import ClassVar, Self

import serde

from .model import Model
from .state import State

type BskyDid = str
type BskyHandle = str


@serde.serde
class BskyCredentials:
    handle: BskyHandle
    password: str
    session: str | None = None


@serde.serde
class User(Model):
    """
    A Telegram user's credentials and preferences.

    `_id` is the Telegram user id, so it survives the bot being used from more
    than one chat.
    """

    COLLECTION: ClassVar[str] = 'users'

    state: State = None
    forward: int | None = None

    bsky: dict[BskyDid, BskyCredentials] = field(default_factory=dict)

    @classmethod
    def resolve(cls, user_id: int) -> Self:
        return cls.one({'_id': user_id}) or cls(_id=user_id)

    @property
    def idle(self) -> bool:
        return self.state is None

    def reset_state(self):
        self.state = None

from typing import ClassVar, Self

import serde

from .model import Model


@serde.serde
class Skip(Model):
    """
    A post a user asked to skip while importing bookmarks.

    `_id` is the pair `'{user}:{url}'` rather than a generated id. polodb can only
    index a single field, so folding the pair into the primary key is what makes
    "one row per user per post" both guaranteed and a point lookup.
    """

    COLLECTION: ClassVar[str] = 'skips'

    @staticmethod
    def key(user: int, url: str) -> str:
        return f'{user}:{url}'

    @classmethod
    def find(cls, user: int, url: str) -> Self | None:
        return cls.one({'_id': cls.key(user, url)})

    @classmethod
    def add(cls, user: int, url: str) -> Self:
        return cls(_id=cls.key(user, url)).save()

    @classmethod
    def remove(cls, user: int, url: str):
        cls(_id=cls.key(user, url)).delete()

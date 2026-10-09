import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Final

from lru import LRU


class GeneratorCache:
    """
    Holds the async generators behind flows that span several messages.

    A generator cannot be serialized, so a flow files one here under an id and keeps
    only that id in its state; a session displaced from the cache is closed, and the
    flow restarts from the top the next time it is used.

    Only `get`, `put` and `discard` are exposed. A bare mapping would also offer
    `clear`/`pop`/`set_size`, which drop a generator without closing it.
    """

    def __init__(self, size: int = 32):
        self.inner: Final = LRU(size, self.on_evict)

    def get(self, rid: str) -> AsyncGenerator[Any, None] | None:
        return self.inner.get(rid)

    def put(self, rid: str, gen: AsyncGenerator[Any, None]):
        self.inner[rid] = gen

    async def discard(self, rid: str):
        gen = self.inner.pop(rid, None)
        if gen is not None:
            await gen.aclose()

    def on_evict(self, rid: str, gen: AsyncGenerator[Any, None]):
        # lru-dict calls this synchronously from `__setitem__`, so the close is handed
        # to the event loop instead of run inline.
        asyncio.create_task(gen.aclose())

import asyncio
import functools
from collections.abc import AsyncGenerator, Callable, Collection
from types import CoroutineType
from typing import Any, Final

from diskcache import ENOVAL
from diskcache import Cache as BaseDiskCache
from diskcache.core import args_to_key, full_name
from lru import LRU

from twitter2album.const import C


class CacheCollection:
    def __init__(self):
        self.gen = GeneratorCache()
        self.disk = DiskCache()


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

    def get(self, rid: str) -> AsyncGenerator[Any] | None:
        return self.inner.get(rid)

    def put(self, rid: str, gen: AsyncGenerator[Any]):
        self.inner[rid] = gen

    async def discard(self, rid: str):
        gen = self.inner.pop(rid, None)
        if gen is not None:
            await gen.aclose()

    def on_evict(self, rid: str, gen: AsyncGenerator[Any]):
        # lru-dict calls this synchronously from `__setitem__`, so the close is handed
        # to the event loop instead of run inline.
        asyncio.create_task(gen.aclose())


class DiskCache(BaseDiskCache):
    def __init__(self):
        C.dirs.cache.mkdir(parents=True, exist_ok=True)
        super().__init__(directory=C.dirs.cache)

    def memoize_async[F: Callable[..., CoroutineType]](
        self,
        name: str | None = None,
        typed: bool = False,
        expire: float | None = None,
        tag: str | None = None,
        ignore: Collection[int | str] = (),
    ) -> Callable[[F], F]:
        def decorator(func):
            base = (full_name(func),) if name is None else (name,)

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                key = args_to_key(base, args, kwargs, typed, ignore)
                result = await asyncio.to_thread(self.get, key, default=ENOVAL, retry=True)

                if result is ENOVAL:
                    result = await func(*args, **kwargs)
                    if expire is None or expire > 0:
                        await asyncio.to_thread(self.set, key, result, expire, tag=tag, retry=True)

                return result

            return wrapper

        return decorator

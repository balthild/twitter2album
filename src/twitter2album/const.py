from pathlib import Path
from types import MappingProxyType
from typing import Final


class Dirs:
    base: Final = Path.cwd() / 'data'

    polodb: Final = base / 'polodb'
    pyrogram: Final = base / 'pyrogram'
    twscrape: Final = base / 'twscrape'


class Domains:
    twitter: Final = frozenset([
        'twitter.com',
        'x.com',
        'fixvx.com',
        'fixupx.com',
        'vxtwitter.com',
        'fxtwitter.com',
    ])

    bsky: Final = frozenset([
        'bsky.app',
    ])


class C:
    dirs: Final = Dirs
    domains: Final = Domains
    platforms: Final = MappingProxyType({
        'twitter': 'Twitter',
        'bsky': 'Bluesky',
    })

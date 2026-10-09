from typing import NamedTuple


class Account(NamedTuple):
    platform: str
    handle: str
    identifier: str

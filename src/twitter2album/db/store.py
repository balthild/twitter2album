from pathlib import Path
from typing import Final, Self

from polodb import PoloDB

from twitter2album.const import C

from .model import Model


class Store:
    """
    Owns the polodb handle and publishes it to `Model`.

    `Model` reads the handle from its own class attribute rather than importing
    this module, which is what keeps the two files from importing each other.
    """

    def __init__(self, path: Path = C.dirs.polodb):
        self.path: Final = path
        self.db: PoloDB | None = None

    async def __aenter__(self) -> Self:
        self.path.mkdir(parents=True, exist_ok=True)
        self.db = PoloDB(self.path)
        Model.db = self.db
        return self

    async def __aexit__(self, *args):
        # Unpublish before closing, so a straggling query fails on the missing
        # handle instead of reaching a closed one.
        Model.db = None
        if self.db is not None:
            self.db.close()
            self.db = None

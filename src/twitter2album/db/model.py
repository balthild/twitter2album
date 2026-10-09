from collections.abc import Iterator
from typing import Any, ClassVar, Self

import serde
from polodb import Collection, PoloDB
from polodb.core import Document, Filter


@serde.serde
class Model:
    """
    Base class for documents stored in a polodb collection.

    Subclasses must declare `COLLECTION` and give every field a default. On read,
    pyserde substitutes the default for any field absent from the document and
    ignores keys it does not recognize, so documents written before a field was
    added keep loading.
    """

    COLLECTION: ClassVar[str]

    # Set by `store.Store` while the database is open.
    db: ClassVar[PoloDB | None] = None

    # polodb echoes back whatever it stored: an int when the caller supplied one,
    # an ObjectId when it generated the id.
    _id: Any = None

    @classmethod
    def collection(cls) -> Collection:
        if cls.db is None:
            raise RuntimeError('The database is not open')

        return cls.db[cls.COLLECTION]

    @classmethod
    def one(cls, filter: Filter | None = None) -> Self | None:
        doc = cls.collection().find_one(filter)
        return None if doc is None else cls.deserialize(doc)

    @classmethod
    def many(
        cls,
        filter: Filter | None = None,
        *,
        skip: int = 0,
        limit: int = 0,
        sort: Filter | None = None,
    ) -> Iterator[Self]:
        docs = cls.collection().find(filter, skip=skip, limit=limit, sort=sort)
        return (cls.deserialize(doc) for doc in docs)

    def save(self) -> Self:
        doc = self.serialize()
        doc.pop('_id', None)

        if self._id is None:
            self._id = self.collection().insert_one(doc).inserted_id
            return self

        # Not `upsert=True`: polodb cannot build a *new* document from an update
        # containing a nested document, it fails with "the field ... is not a
        # valid field name". Updating and inserting separately avoids that path,
        # and the unique index on _id rejects a duplicate if one races in.
        updated = self.collection().update_one({'_id': self._id}, {'$set': doc})
        if updated.matched_count == 0:
            self.collection().insert_one({'_id': self._id, **doc})

        return self

    def delete(self):
        if self._id is not None:
            self.collection().delete_one({'_id': self._id})

    def serialize(self) -> Document:
        return serde.to_dict(self)

    @classmethod
    def deserialize(cls, values: Document) -> Self:
        return serde.from_dict(cls, values)

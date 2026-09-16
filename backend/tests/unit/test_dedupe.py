"""Unit tests for dedupe.py — a lightweight in-memory fake standing in for the
boilerplate_cache table (real Postgres round-trip is covered by
tests/integration/test_ingestion_integration.py once boilerplate content repeats
across a real ingestion run).
"""

import uuid

from app.models.boilerplate_cache import BoilerplateCache
from app.pipeline import dedupe


class FakeDedupeSession:
    def __init__(self) -> None:
        self.store: dict[str, BoilerplateCache] = {}

    def get(self, model, pk):
        return self.store.get(pk)

    def add(self, obj) -> None:
        self.store[obj.content_hash] = obj

    def commit(self) -> None:
        pass

    def query(self, model):
        return _FakeQuery(list(self.store.values()))


class _FakeQuery:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


def test_first_sighting_creates_a_row_and_is_not_a_hit() -> None:
    db = FakeDedupeSession()
    document_id = uuid.uuid4()

    was_hit = dedupe.check_and_record(db, "hash-abc", document_id, "some clause text")

    assert was_hit is False
    assert "hash-abc" in db.store
    assert db.store["hash-abc"].hit_count == 0
    assert db.store["hash-abc"].first_seen_document_id == document_id


def test_second_sighting_increments_hit_count() -> None:
    db = FakeDedupeSession()
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()

    dedupe.check_and_record(db, "shared-hash", doc_a, "boilerplate clause")
    was_hit = dedupe.check_and_record(db, "shared-hash", doc_b, "boilerplate clause")

    assert was_hit is True
    assert db.store["shared-hash"].hit_count == 1


def test_hit_count_totals_across_multiple_duplicates() -> None:
    db = FakeDedupeSession()
    doc_ids = [uuid.uuid4() for _ in range(4)]

    for doc_id in doc_ids:
        dedupe.check_and_record(db, "repeated-clause", doc_id, "text")

    # First sighting doesn't count as a hit; the next 3 do.
    assert dedupe.hit_count(db) == 3


def test_different_content_does_not_cross_contaminate() -> None:
    db = FakeDedupeSession()
    dedupe.check_and_record(db, "hash-1", uuid.uuid4(), "clause one")
    dedupe.check_and_record(db, "hash-2", uuid.uuid4(), "clause two")

    assert dedupe.hit_count(db) == 0
    assert len(db.store) == 2

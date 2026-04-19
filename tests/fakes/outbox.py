"""In-memory outbox fakes for unit tests.

- ``InMemoryOutboxPublisher`` records every ``enqueue`` call for test inspection.
- ``InMemoryOutboxReader`` mirrors the SQL reader's claim/mark interface
  against the same backing list. Tests can drive the relay loop end-to-end
  without touching Postgres.

Both share the same ``entries`` list so a publisher enqueue becomes visible
to the reader immediately — mimicking the "same transaction" semantics the
SA pair gets for free by using the same session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from typing import Any


@dataclass
class _OutboxEntry:
    id: int
    created_at: datetime
    channel: str
    subject: str
    payload: dict[str, Any]
    published_at: datetime | None = None
    attempts: int = 0


@dataclass
class _OutboxStore:
    """Shared backing list so publisher + reader see the same rows."""

    entries: list[_OutboxEntry] = field(default_factory=list)
    _ids: count[int] = field(default_factory=lambda: count(start=1))


class InMemoryOutboxPublisher:
    """Fake publisher. Records every enqueue in ``self.store.entries``."""

    def __init__(self, store: _OutboxStore | None = None) -> None:
        self.store = store or _OutboxStore()

    @property
    def enqueued(self) -> list[_OutboxEntry]:
        """Every entry, in enqueue order. Convenience for assertions."""
        return list(self.store.entries)

    async def enqueue(
        self,
        session: Any,
        *,
        channel: str,
        subject: str,
        payload: dict[str, Any],
    ) -> None:
        self.store.entries.append(
            _OutboxEntry(
                id=next(self.store._ids),
                created_at=datetime.now(tz=UTC),
                channel=channel,
                subject=subject,
                payload=payload,
            )
        )


class InMemoryOutboxReader:
    """Fake reader. Shares a store with the publisher so tests can round-trip
    enqueue → claim → mark_published and assert on final state.
    """

    def __init__(self, store: _OutboxStore) -> None:
        self.store = store

    async def claim_batch(
        self,
        session: Any,
        *,
        limit: int = 100,
        commit_visibility_lag_ms: int = 100,
    ) -> list[_OutboxEntry]:
        pending = [e for e in self.store.entries if e.published_at is None]
        return pending[:limit]

    async def mark_published(
        self,
        session: Any,
        *,
        ids: list[tuple[int, datetime]],
        published_at: datetime,
    ) -> None:
        id_set = {row_id for row_id, _ in ids}
        for entry in self.store.entries:
            if entry.id in id_set:
                entry.published_at = published_at
                entry.attempts += 1

    async def increment_attempts(
        self,
        session: Any,
        *,
        ids: list[tuple[int, datetime]],
    ) -> None:
        id_set = {row_id for row_id, _ in ids}
        for entry in self.store.entries:
            if entry.id in id_set:
                entry.attempts += 1


def make_outbox_pair() -> tuple[InMemoryOutboxPublisher, InMemoryOutboxReader]:
    """Factory for a linked publisher + reader pair sharing one store."""
    store = _OutboxStore()
    return InMemoryOutboxPublisher(store), InMemoryOutboxReader(store)

"""Pure-unit tests for the in-memory outbox fakes.

The publisher and reader share a store so an enqueue is immediately visible
to claim_batch — mirroring the transactional semantics the SQL pair gets.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.fakes import make_outbox_pair


@pytest.mark.asyncio
async def test_claim_batch_returns_unpublished_entries():
    publisher, reader = make_outbox_pair()

    await publisher.enqueue(None, channel="c1", subject="c1", payload={"n": 1})
    await publisher.enqueue(None, channel="c2", subject="c2", payload={"n": 2})

    claimed = await reader.claim_batch(None, limit=10)
    assert [e.payload["n"] for e in claimed] == [1, 2]


@pytest.mark.asyncio
async def test_claim_batch_respects_limit():
    publisher, reader = make_outbox_pair()
    for i in range(5):
        await publisher.enqueue(None, channel="c", subject="c", payload={"i": i})

    claimed = await reader.claim_batch(None, limit=2)
    assert len(claimed) == 2


@pytest.mark.asyncio
async def test_mark_published_excludes_from_subsequent_claim():
    publisher, reader = make_outbox_pair()
    await publisher.enqueue(None, channel="c", subject="c", payload={"n": 1})
    await publisher.enqueue(None, channel="c", subject="c", payload={"n": 2})

    first_batch = await reader.claim_batch(None, limit=10)
    await reader.mark_published(
        None,
        ids=[(e.id, e.created_at) for e in first_batch],
        published_at=datetime.now(tz=UTC),
    )

    second_batch = await reader.claim_batch(None, limit=10)
    assert second_batch == []


@pytest.mark.asyncio
async def test_mark_published_sets_attempts():
    publisher, reader = make_outbox_pair()
    await publisher.enqueue(None, channel="c", subject="c", payload={})
    [entry] = await reader.claim_batch(None)
    await reader.mark_published(
        None,
        ids=[(entry.id, entry.created_at)],
        published_at=datetime.now(tz=UTC),
    )
    assert entry.attempts == 1


@pytest.mark.asyncio
async def test_increment_attempts_keeps_entry_unpublished():
    publisher, reader = make_outbox_pair()
    await publisher.enqueue(None, channel="c", subject="c", payload={})
    [entry] = await reader.claim_batch(None)
    await reader.increment_attempts(None, ids=[(entry.id, entry.created_at)])
    assert entry.attempts == 1
    assert entry.published_at is None
    # Still eligible for re-claim.
    assert (await reader.claim_batch(None))[0].id == entry.id

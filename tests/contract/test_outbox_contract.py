"""Contract tests for :class:`ascent.ports.OutboxPublisher`.

Fake-backed invariants the publisher must honor. Durability (commit/rollback
semantics) is covered in the integration tests against real Postgres.
"""

from __future__ import annotations

import pytest

from ascent.ports import OutboxPublisher
from tests.fakes import InMemoryOutboxPublisher


@pytest.fixture
def publisher() -> InMemoryOutboxPublisher:
    return InMemoryOutboxPublisher()


@pytest.mark.asyncio
async def test_enqueue_appends_to_store(publisher, session):
    await publisher.enqueue(
        session,
        channel="ascent.exchange.abc",
        subject="ascent.exchange.abc",
        payload={"action": "submit_order", "order_id": "1"},
    )
    assert len(publisher.enqueued) == 1
    entry = publisher.enqueued[0]
    assert entry.channel == "ascent.exchange.abc"
    assert entry.payload == {"action": "submit_order", "order_id": "1"}
    assert entry.published_at is None


@pytest.mark.asyncio
async def test_enqueue_assigns_monotonic_ids(publisher, session):
    for i in range(3):
        await publisher.enqueue(session, channel="c", subject="s", payload={"i": i})
    ids = [e.id for e in publisher.enqueued]
    assert ids == sorted(ids)
    assert len(set(ids)) == 3


@pytest.mark.asyncio
async def test_publisher_is_instance_of_protocol(publisher):
    assert isinstance(publisher, OutboxPublisher)

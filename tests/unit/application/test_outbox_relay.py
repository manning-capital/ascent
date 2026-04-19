"""Unit tests for :class:`OutboxRelay`.

All tests use the in-memory outbox pair and ``FakeDurablePublisher`` — no
real DB or broker. The important invariants to pin down:

- An empty outbox is a no-op (returns 0, does not sleep forever on publish).
- ``drain_once`` publishes every claimed row then marks them all published.
- A failed publish leaves the row unpublished and increments ``attempts``.
- A partial failure publishes the successful rows and retries only the failures.
- Re-running the relay after a simulated crash between publish-and-mark does
  NOT double-publish (the fake publisher dedups on ``msg_id``, mirroring
  JetStream's ``Nats-Msg-Id`` behavior).
- Rows are published in FIFO order.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ascent.application.outbox_relay import OutboxRelay
from tests.fakes import (
    FakeClock,
    FakeDurablePublisher,
    FakeUnitOfWorkFactory,
    make_outbox_pair,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _relay(*, dedup: bool = True) -> tuple[OutboxRelay, FakeDurablePublisher, object, object]:
    uow_factory = FakeUnitOfWorkFactory()
    publisher, reader = make_outbox_pair()
    pub = FakeDurablePublisher(dedup=dedup)
    relay = OutboxRelay(
        uow_factory=uow_factory,
        reader=reader,
        publisher=pub,
        clock=FakeClock(NOW),
    )
    return relay, pub, publisher, reader


@pytest.mark.asyncio
async def test_drain_once_on_empty_outbox_returns_zero():
    relay, pub, _, _ = _relay()
    assert await relay.drain_once() == 0
    assert pub.published == []


@pytest.mark.asyncio
async def test_drain_once_publishes_every_claimed_row():
    relay, pub, outbox_pub, _ = _relay()
    for i in range(3):
        await outbox_pub.enqueue(None, channel="c", subject="ascent.exchange.x", payload={"i": i})

    published = await relay.drain_once()
    assert published == 3
    assert len(pub.published) == 3
    assert [p.payload["i"] for p in pub.published] == [0, 1, 2]


@pytest.mark.asyncio
async def test_drain_once_marks_published_so_second_pass_is_noop():
    relay, pub, outbox_pub, reader = _relay()
    await outbox_pub.enqueue(None, channel="c", subject="s", payload={})
    assert await relay.drain_once() == 1
    assert await relay.drain_once() == 0  # nothing left to claim
    assert len(pub.published) == 1


@pytest.mark.asyncio
async def test_failed_publish_leaves_row_unpublished_and_increments_attempts():
    relay, pub, outbox_pub, reader = _relay()
    await outbox_pub.enqueue(None, channel="c", subject="s", payload={"v": 1})

    pub.fail_next = RuntimeError("broker down")
    published = await relay.drain_once()
    assert published == 0
    # The row is still unpublished with attempts=1.
    remaining = await reader.claim_batch(None)
    assert len(remaining) == 1
    assert remaining[0].attempts == 1

    # Next pass succeeds.
    published = await relay.drain_once()
    assert published == 1


@pytest.mark.asyncio
async def test_partial_failure_publishes_successes_and_retries_failures():
    """One broken publish in a batch must not stop the others from landing."""
    relay, pub, outbox_pub, reader = _relay()
    for i in range(3):
        await outbox_pub.enqueue(None, channel="c", subject="s", payload={"i": i})

    # fail_next fires on the first publish (i=0) and clears itself, so
    # subsequent publishes in the same batch succeed.
    pub.fail_next = RuntimeError("transient")
    published = await relay.drain_once()
    assert published == 2
    assert {p.payload["i"] for p in pub.published} == {1, 2}

    # Only the failed row (i=0) should remain claimable.
    remaining = await reader.claim_batch(None)
    assert len(remaining) == 1
    assert remaining[0].payload["i"] == 0


@pytest.mark.asyncio
async def test_dedup_prevents_double_publish_on_simulated_crash():
    """Model a relay crash between publish() and mark_published():

    1. drain_once publishes a row but crashes before marking — simulate by
       raising from inside mark_published via an exception the UoW sees.

    We simulate by manually driving the steps rather than hooking
    mark_published, which is simpler and still exercises the dedup guarantee.
    """
    relay, pub, outbox_pub, reader = _relay(dedup=True)
    await outbox_pub.enqueue(None, channel="c", subject="s", payload={"v": 1})

    # First pass: publish lands, mark_published runs, row drops out.
    assert await relay.drain_once() == 1
    assert len(pub.published) == 1

    # Now directly simulate "relay restarted and row was never marked":
    # reset the entries' published_at to None so the row is claimable again.
    for entry in outbox_pub.store.entries:
        entry.published_at = None

    # Second pass re-publishes but the fake publisher dedups on msg_id.
    assert await relay.drain_once() == 1  # the relay *did* publish one row
    # …but the broker only kept one copy thanks to dedup.
    assert len(pub.published) == 1


@pytest.mark.asyncio
async def test_without_dedup_crash_recovery_causes_duplicate():
    """Document the Redis-shim's weaker behavior: without broker dedup, a
    crash-recovery re-publish DOES produce a duplicate. This is why phase-5
    replaces the shim with JetStream."""
    relay, pub, outbox_pub, _ = _relay(dedup=False)
    await outbox_pub.enqueue(None, channel="c", subject="s", payload={"v": 1})

    await relay.drain_once()
    for entry in outbox_pub.store.entries:
        entry.published_at = None
    await relay.drain_once()

    assert len(pub.published) == 2  # duplicate — this is the shim's known weakness

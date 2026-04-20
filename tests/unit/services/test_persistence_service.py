"""Runtime tests for :class:`PersistenceService`.

This is the "outbox": strategies see fresh data via Redis; durable writes
happen off the hot path here. Verifies that publishing a feed event causes
a matching historical upsert.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import uuid

import pandas as pd
import pytest

from ascent.application import FeedPersister, PersistenceService
from tests.fakes import InMemoryEventBus, InMemoryFeedStore


class FakeAttributeResolver:
    """Test double mapping attribute name -> UUID; unknown names -> None."""

    def __init__(self, mapping: dict[str, uuid.UUID]) -> None:
        self._mapping = mapping

    def attribute_id_for_name(self, name: str) -> uuid.UUID | None:
        return self._mapping.get(name)


async def _wait(predicate, *, timeout: float = 1.0):
    for _ in range(int(timeout * 200)):
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"predicate stayed falsy for {timeout}s")


async def _let_service_subscribe(bus, channel, *, timeout: float = 0.5):
    """Wait until a service's subscription has been registered on the bus.
    Prevents a publish-before-subscribe race — pub/sub is lossy, so we must
    publish only after the subscriber is actually on the channel.
    """
    for _ in range(int(timeout * 200)):
        if bus._subscribers.get(channel):
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"service never subscribed to {channel}")


@pytest.mark.asyncio
async def test_feed_event_triggers_upsert():
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    feed_id = uuid.uuid4()
    output_table = "instrument_attribute"
    channel = f"ascent.feed.{feed_id}"
    close_id = uuid.uuid4()
    volume_id = uuid.uuid4()
    partition_ts = "2026-04-16T12:00:00+00:00"

    df = pd.DataFrame(
        [
            {"instrument_id": str(uuid.uuid4()), "CLOSE": 1.0, "VOLUME": 100.0},
            {"instrument_id": str(uuid.uuid4()), "CLOSE": 2.0, "VOLUME": 200.0},
        ]
    )
    await store.put_latest(
        feed_id,
        df,
        produced_at=_dt.datetime.fromisoformat(partition_ts),
    )

    persister = FeedPersister(
        latest_store=store,
        historical_store=store,
        attribute_resolver=FakeAttributeResolver({"CLOSE": close_id, "VOLUME": volume_id}),
    )
    service = PersistenceService(
        feed_channels=[channel],
        feed_id_to_output={feed_id: output_table},
        event_bus=bus,
        persister=persister,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        await _let_service_subscribe(bus, channel)
        await bus.publish(
            channel,
            {
                "feed_id": str(feed_id),
                "schema": output_table,
                "snapshot_timestamp": partition_ts,
            },
        )
        await _wait(lambda: len(store.upserts) == 1)
        fid, table, rows = store.upserts[0]
        assert fid == feed_id
        assert table == output_table
        # 2 entities × 2 attributes = 4 melted rows
        assert rows == 4
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_upsert_uses_schema_from_event_when_no_override():
    """If the feed isn't in the override map, the ``schema`` field from the
    published event is used as the table name.
    """
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    feed_id = uuid.uuid4()
    channel = f"ascent.feed.{feed_id}"
    close_id = uuid.uuid4()
    partition_ts = "2026-04-16T12:00:00+00:00"

    await store.put_latest(
        feed_id,
        pd.DataFrame([{"composite_id": str(uuid.uuid4()), "CLOSE": 1.0}]),
        produced_at=_dt.datetime.fromisoformat(partition_ts),
    )

    persister = FeedPersister(
        latest_store=store,
        historical_store=store,
        attribute_resolver=FakeAttributeResolver({"CLOSE": close_id}),
    )
    service = PersistenceService(
        feed_channels=[channel],
        feed_id_to_output={},
        event_bus=bus,
        persister=persister,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        await _let_service_subscribe(bus, channel)
        await bus.publish(
            channel,
            {
                "feed_id": str(feed_id),
                "schema": "composite_attribute",
                "snapshot_timestamp": partition_ts,
            },
        )
        await _wait(lambda: len(store.upserts) == 1)
        _, table, _ = store.upserts[0]
        assert table == "composite_attribute"
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_empty_payload_is_dropped_safely():
    """A feed event with no ``schema`` and no override shouldn't crash — it
    just isn't persisted.
    """
    store = InMemoryFeedStore()
    bus = InMemoryEventBus()
    feed_id = uuid.uuid4()
    channel = f"ascent.feed.{feed_id}"

    persister = FeedPersister(
        latest_store=store,
        historical_store=store,
        attribute_resolver=FakeAttributeResolver({}),
    )
    service = PersistenceService(
        feed_channels=[channel],
        feed_id_to_output={},
        event_bus=bus,
        persister=persister,
    )
    task = asyncio.create_task(service.run_forever())
    try:
        await bus.publish(channel, {"feed_id": str(feed_id)})
        await asyncio.sleep(0.05)
        assert store.upserts == []
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

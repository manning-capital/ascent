"""Redis-backed adapter conformance tests.

Same kind of test as the SQL conformance suite, but against real Redis. The
adapters here (``RedisEventBus``, ``RedisFeedCache``, ``RedisHeartbeat``)
round-trip payloads through Redis pub/sub and JSON — the fakes bypass both.
These tests prove the real adapter actually does what the port says it does.

Hot failure modes we're guarding against:

- DataFrame dtypes shifting through JSON round-trip (``attribute_value`` as
  ``str`` would crash downstream ``.astype(float)`` calls).
- Pub/sub channel bytes vs. str (``decode_responses=True`` flag flipping).
- Heartbeat TTL expiry not firing, causing dead entities to appear alive.
"""

from __future__ import annotations

import asyncio
import uuid

import pandas as pd
import pytest
import pytest_asyncio

from ascent.adapters.redis_asyncio import (
    RedisEventBus,
    RedisFeedCache,
    RedisHeartbeat,
    create_redis_client,
)


@pytest_asyncio.fixture
async def redis_client(redis_url):
    client = create_redis_client(redis_url)
    try:
        yield client
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


async def _drain_next(subscription, *, timeout: float = 2.0):
    return await asyncio.wait_for(subscription.__anext__(), timeout=timeout)


@pytest.mark.asyncio
async def test_redis_event_bus_round_trips_payload(redis_client):
    bus = RedisEventBus(redis_client)
    channel = f"ascent.test.{uuid.uuid4().hex[:8]}"

    sub = bus.subscribe([channel])
    task = asyncio.create_task(_drain_next(sub))
    # Let Redis SUBSCRIBE complete before publishing — pub/sub is lossy.
    await asyncio.sleep(0.1)

    await bus.publish(channel, {"hello": "world", "n": 42})
    event = await task

    assert event.channel == channel
    assert event.payload == {"hello": "world", "n": 42}
    await sub.aclose()


@pytest.mark.asyncio
async def test_redis_event_bus_isolates_channels(redis_client):
    bus = RedisEventBus(redis_client)
    ch_a = f"ascent.test.a.{uuid.uuid4().hex[:8]}"
    ch_b = f"ascent.test.b.{uuid.uuid4().hex[:8]}"

    sub = bus.subscribe([ch_a])
    task = asyncio.create_task(_drain_next(sub))
    await asyncio.sleep(0.1)

    await bus.publish(ch_b, {"leak": True})
    await bus.publish(ch_a, {"leak": False})

    event = await task
    # The subscriber on ch_a must ONLY see ch_a — not the leaked message.
    assert event.channel == ch_a
    assert event.payload == {"leak": False}
    await sub.aclose()


# ---------------------------------------------------------------------------
# FeedCache
# ---------------------------------------------------------------------------


def _eav_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-04-16T12:00:00+00:00",
                "instrument_id": str(uuid.uuid4()),
                "attribute_id": str(uuid.uuid4()),
                "attribute_value": 123.45,
            },
            {
                "timestamp": "2026-04-16T12:00:01+00:00",
                "instrument_id": str(uuid.uuid4()),
                "attribute_id": str(uuid.uuid4()),
                "attribute_value": 67.89,
            },
        ]
    )


@pytest.mark.asyncio
async def test_redis_feed_cache_preserves_columns_and_values(redis_client):
    cache = RedisFeedCache(redis_client)
    feed_id = uuid.uuid4()
    df = _eav_df()

    await cache.put_latest(feed_id, df, produced_at=pd.Timestamp.utcnow())
    fetched = await cache.get_latest(feed_id)

    assert fetched is not None
    assert list(fetched.columns) == [
        "timestamp",
        "instrument_id",
        "attribute_id",
        "attribute_value",
    ]
    # attribute_value must survive as a numeric — the context builder later
    # does float arithmetic on it. If the JSON round-trip stringified it,
    # strategies would silently break.
    assert fetched["attribute_value"].tolist() == [123.45, 67.89]


@pytest.mark.asyncio
async def test_redis_feed_cache_get_latest_many_mirrors_puts(redis_client):
    cache = RedisFeedCache(redis_client)
    have = uuid.uuid4()
    missing = uuid.uuid4()
    await cache.put_latest(have, _eav_df(), produced_at=pd.Timestamp.utcnow())

    out = await cache.get_latest_many([have, missing])
    assert out[missing] is None
    assert out[have] is not None
    assert len(out[have]) == 2


@pytest.mark.asyncio
async def test_redis_feed_cache_is_warm(redis_client):
    cache = RedisFeedCache(redis_client)
    feed_id = uuid.uuid4()
    assert not await cache.is_warm(feed_id)
    await cache.put_latest(feed_id, _eav_df(), produced_at=pd.Timestamp.utcnow())
    assert await cache.is_warm(feed_id)


# ---------------------------------------------------------------------------
# HeartbeatStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_heartbeat_touch_then_alive(redis_client):
    hb = RedisHeartbeat(redis_client)
    eid = uuid.uuid4()

    assert not await hb.is_alive("feed", eid)
    await hb.touch("feed", eid, ttl_seconds=30)
    assert await hb.is_alive("feed", eid)


@pytest.mark.asyncio
async def test_redis_heartbeat_ttl_expiry(redis_client):
    """TTL is the whole point of using Redis for liveness — prove it expires.

    We use a 1s TTL to keep the test quick; real deployments use 30s.
    """
    hb = RedisHeartbeat(redis_client)
    eid = uuid.uuid4()

    await hb.touch("feed", eid, ttl_seconds=1)
    assert await hb.is_alive("feed", eid)

    # Wait past the TTL and re-check.
    await asyncio.sleep(1.2)
    assert not await hb.is_alive("feed", eid)


@pytest.mark.asyncio
async def test_redis_heartbeat_batch_statuses(redis_client):
    hb = RedisHeartbeat(redis_client)
    alive = uuid.uuid4()
    dead = uuid.uuid4()
    await hb.touch("strategy", alive, ttl_seconds=30)

    statuses = await hb.statuses("strategy", [alive, dead])
    assert statuses == {alive: True, dead: False}

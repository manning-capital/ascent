"""Tests for Redis heartbeat — set, get, expire, batch check."""

import time
import uuid


def test_set_heartbeat_creates_key(engine_cache):
    """set_heartbeat() creates a Redis key with TTL."""
    feed_id = uuid.uuid4()
    engine_cache.set_heartbeat("feed", feed_id, ttl=10)

    assert engine_cache.is_connected("feed", feed_id) is True


def test_heartbeat_expires(engine_cache):
    """Heartbeat key expires after TTL."""
    feed_id = uuid.uuid4()
    engine_cache.set_heartbeat("feed", feed_id, ttl=1)

    assert engine_cache.is_connected("feed", feed_id) is True
    time.sleep(1.5)
    assert engine_cache.is_connected("feed", feed_id) is False


def test_is_connected_false_when_no_key(engine_cache):
    """is_connected() returns False when no heartbeat key."""
    feed_id = uuid.uuid4()
    assert engine_cache.is_connected("feed", feed_id) is False


def test_get_heartbeat_returns_timestamp(engine_cache):
    """get_heartbeat() returns an ISO timestamp string."""
    feed_id = uuid.uuid4()
    engine_cache.set_heartbeat("feed", feed_id, ttl=10)

    ts = engine_cache.get_heartbeat("feed", feed_id)
    assert ts is not None
    assert "T" in ts  # ISO format


def test_get_heartbeat_returns_none_when_missing(engine_cache):
    """get_heartbeat() returns None for missing keys."""
    assert engine_cache.get_heartbeat("feed", uuid.uuid4()) is None


def test_get_connection_statuses_batch(engine_cache):
    """get_connection_statuses() batch-checks multiple IDs."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()

    engine_cache.set_heartbeat("feed", id1, ttl=10)
    engine_cache.set_heartbeat("feed", id3, ttl=10)
    # id2 has no heartbeat

    statuses = engine_cache.get_connection_statuses("feed", [id1, id2, id3])
    assert statuses[id1] is True
    assert statuses[id2] is False
    assert statuses[id3] is True


def test_get_connection_statuses_empty(engine_cache):
    """get_connection_statuses() returns empty dict for empty input."""
    assert engine_cache.get_connection_statuses("feed", []) == {}


def test_heartbeat_strategy_type(engine_cache):
    """Heartbeat works for strategy entity type."""
    strategy_id = uuid.uuid4()
    engine_cache.set_heartbeat("strategy", strategy_id, ttl=10)
    assert engine_cache.is_connected("strategy", strategy_id) is True
    assert engine_cache.is_connected("feed", strategy_id) is False  # different namespace

"""Contract tests for :class:`ascent.ports.EventBus`.

Key invariants we assert against every backend:

- publish → subscribe round-trips the payload unchanged
- fanout: multiple subscribers on the same channel each receive every event
- channel isolation: an event on channel A never leaks to a subscriber on B only
- pub/sub is lossy: events published before anyone subscribed are dropped
  (matches Redis semantics — the bus is not a queue)
- ``aclose`` on a subscription releases any underlying resources
"""

from __future__ import annotations

import asyncio

import pytest


async def _next_event(subscription, *, timeout: float = 1.0):
    """Pull the next event with a timeout so tests fail fast if nothing comes."""
    return await asyncio.wait_for(subscription.__anext__(), timeout=timeout)


class TestPublishAndSubscribe:
    @pytest.mark.asyncio
    async def test_subscriber_receives_published_payload(self, event_bus):
        sub = event_bus.subscribe(["ch.a"])

        await event_bus.publish("ch.a", {"hello": "world", "n": 42})
        event = await _next_event(sub)

        assert event.channel == "ch.a"
        assert event.payload == {"hello": "world", "n": 42}
        await _aclose(sub)

    @pytest.mark.asyncio
    async def test_multiple_channels_route_independently(self, event_bus):
        sub_a = event_bus.subscribe(["ch.a"])
        sub_b = event_bus.subscribe(["ch.b"])

        await event_bus.publish("ch.a", {"which": "a"})
        await event_bus.publish("ch.b", {"which": "b"})

        event_a = await _next_event(sub_a)
        event_b = await _next_event(sub_b)
        assert event_a.payload == {"which": "a"}
        assert event_b.payload == {"which": "b"}
        await _aclose(sub_a)
        await _aclose(sub_b)

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_channels_receives_from_each(self, event_bus):
        sub = event_bus.subscribe(["ch.a", "ch.b"])

        await event_bus.publish("ch.a", {"one": 1})
        await event_bus.publish("ch.b", {"two": 2})

        # Collect both events; ordering across channels is not guaranteed.
        seen = []
        for _ in range(2):
            event = await _next_event(sub)
            seen.append((event.channel, event.payload))
        assert ("ch.a", {"one": 1}) in seen
        assert ("ch.b", {"two": 2}) in seen
        await _aclose(sub)


class TestFanout:
    @pytest.mark.asyncio
    async def test_multiple_subscribers_each_receive_every_event(self, event_bus):
        sub_a = event_bus.subscribe(["ch.broadcast"])
        sub_b = event_bus.subscribe(["ch.broadcast"])

        await event_bus.publish("ch.broadcast", {"msg": "hi"})

        event_a = await _next_event(sub_a)
        event_b = await _next_event(sub_b)
        assert event_a.payload == {"msg": "hi"}
        assert event_b.payload == {"msg": "hi"}
        await _aclose(sub_a)
        await _aclose(sub_b)


class TestLossySemantics:
    @pytest.mark.asyncio
    async def test_publish_before_subscribe_is_dropped(self, event_bus):
        """Pub/sub is not a queue — events without a subscriber are lost.
        This matches Redis pub/sub and keeps the engine behaviour deterministic.
        """
        await event_bus.publish("ch.early", {"missed": True})

        sub = event_bus.subscribe(["ch.early"])
        # Subsequent event arrives normally; the earlier one is gone.
        await event_bus.publish("ch.early", {"missed": False})
        event = await _next_event(sub)
        assert event.payload == {"missed": False}
        await _aclose(sub)


class TestIsolation:
    @pytest.mark.asyncio
    async def test_subscriber_does_not_see_other_channels(self, event_bus):
        sub = event_bus.subscribe(["ch.mine"])

        await event_bus.publish("ch.other", {"leak": True})
        await event_bus.publish("ch.mine", {"leak": False})

        event = await _next_event(sub)
        # We must ONLY see ch.mine payload — not the leaked one.
        assert event.channel == "ch.mine"
        assert event.payload == {"leak": False}
        await _aclose(sub)


class TestAclose:
    @pytest.mark.asyncio
    async def test_aclose_releases_subscription(self, event_bus):
        sub = event_bus.subscribe(["ch.close"])
        await event_bus.publish("ch.close", {"n": 1})
        assert (await _next_event(sub)).payload == {"n": 1}

        await _aclose(sub)

        # After aclose, publishing again shouldn't deliver to this (closed) sub.
        # Re-subscribing starts fresh.
        sub2 = event_bus.subscribe(["ch.close"])
        await event_bus.publish("ch.close", {"n": 2})
        assert (await _next_event(sub2)).payload == {"n": 2}
        await _aclose(sub2)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _aclose(subscription) -> None:
    aclose = getattr(subscription, "aclose", None)
    if aclose is not None:
        await aclose()

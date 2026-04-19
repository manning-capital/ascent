"""Redis adapters using :mod:`redis.asyncio`.

All four Redis-backed ports live here because they share the same client
instance and serialization conventions.
"""

from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pandas as pd
import redis.asyncio as aioredis

from ascent.ports import Event, EventBus, HeartbeatStore, LatestFeedStore, StateStore
from ascent.ports.durable_publisher import DurablePublisher


class _RedisBase:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class RedisEventBus(_RedisBase, EventBus):
    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        await self._redis.publish(channel, json.dumps(payload))

    def subscribe(self, channels: list[str]) -> AsyncIterator[Event]:
        return _RedisSubscription(self._redis, channels)


class _RedisSubscription:
    def __init__(self, redis: aioredis.Redis, channels: list[str]) -> None:
        self._redis = redis
        self._channels = channels
        self._pubsub: Any = None

    def __aiter__(self) -> _RedisSubscription:
        return self

    async def __anext__(self) -> Event:
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(*self._channels)
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            payload = json.loads(message["data"])
            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode()
            return Event(channel=channel, payload=payload)

    async def aclose(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()


# ---------------------------------------------------------------------------
# Feed cache (LatestFeedStore)
# ---------------------------------------------------------------------------


class RedisFeedCache(_RedisBase, LatestFeedStore):
    @staticmethod
    def _key(feed_id: uuid.UUID) -> str:
        return f"ascent:feed:{feed_id}:latest"

    @staticmethod
    def _ts_key(feed_id: uuid.UUID) -> str:
        return f"ascent:feed:{feed_id}:updated_at"

    async def put_latest(
        self, feed_id: uuid.UUID, df: pd.DataFrame, produced_at: datetime.datetime
    ) -> None:
        data = df.to_json(orient="records", date_format="iso")
        async with self._redis.pipeline() as pipe:
            await (
                pipe.set(self._key(feed_id), data)
                .set(self._ts_key(feed_id), produced_at.isoformat())
                .execute()
            )

    async def get_latest(self, feed_id: uuid.UUID) -> pd.DataFrame | None:
        raw = await self._redis.get(self._key(feed_id))
        if raw is None:
            return None
        return pd.DataFrame(json.loads(raw))

    async def get_latest_many(
        self, feed_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, pd.DataFrame | None]:
        if not feed_ids:
            return {}
        keys = [self._key(fid) for fid in feed_ids]
        values = await self._redis.mget(keys)
        result: dict[uuid.UUID, pd.DataFrame | None] = {}
        for fid, raw in zip(feed_ids, values, strict=True):
            if raw is None:
                result[fid] = None
            else:
                result[fid] = pd.DataFrame(json.loads(raw))
        return result

    async def is_warm(self, feed_id: uuid.UUID) -> bool:
        return bool(await self._redis.exists(self._key(feed_id)))


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------


class RedisStateStore(_RedisBase, StateStore):
    @staticmethod
    def _key(strategy_id: uuid.UUID) -> str:
        return f"ascent:strategy:{strategy_id}:state"

    async def get(self, strategy_id: uuid.UUID) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(strategy_id))
        return None if raw is None else json.loads(raw)

    async def set(self, strategy_id: uuid.UUID, state: dict[str, Any]) -> None:
        await self._redis.set(self._key(strategy_id), json.dumps(state))


# ---------------------------------------------------------------------------
# HeartbeatStore
# ---------------------------------------------------------------------------


class RedisHeartbeat(_RedisBase, HeartbeatStore):
    @staticmethod
    def _key(entity_type: str, entity_id: uuid.UUID) -> str:
        return f"ascent:heartbeat:{entity_type}:{entity_id}"

    async def touch(self, entity_type: str, entity_id: uuid.UUID, *, ttl_seconds: int = 30) -> None:
        await self._redis.setex(
            self._key(entity_type, entity_id),
            ttl_seconds,
            datetime.datetime.now(tz=datetime.UTC).isoformat(),
        )

    async def is_alive(self, entity_type: str, entity_id: uuid.UUID) -> bool:
        return bool(await self._redis.exists(self._key(entity_type, entity_id)))

    async def statuses(
        self, entity_type: str, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, bool]:
        if not entity_ids:
            return {}
        async with self._redis.pipeline() as pipe:
            for eid in entity_ids:
                pipe.exists(self._key(entity_type, eid))
            results = await pipe.execute()
        return {eid: bool(r) for eid, r in zip(entity_ids, results, strict=True)}


def create_redis_client(redis_url: str) -> aioredis.Redis:
    """Factory — keeps ``decode_responses=True`` consistent across adapters."""
    return aioredis.from_url(redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# DurablePublisher (Redis pub/sub shim)
# ---------------------------------------------------------------------------


class RedisDurablePublisher(DurablePublisher):
    """Temporary phase-4 shim. Forwards outbox rows to the Redis event bus
    so existing subscribers keep working until the JetStream stack lands.

    Redis pub/sub has no dedup — if the relay re-publishes after a crash,
    downstream consumers will see the event twice. This is **not** a
    production-safe durable publisher; it only exists to let us wire and
    test the outbox → relay flow before introducing NATS.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    async def publish(self, subject: str, payload: dict[str, Any], *, msg_id: str) -> None:
        # msg_id is discarded — the shim has no dedup. Real impl (JetStream)
        # uses ``Nats-Msg-Id`` for 2-minute dedup windows.
        del msg_id
        await self._bus.publish(subject, payload)

"""EngineCache — Redis-backed cache for feed data, strategy state, and pub/sub."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pandas as pd
import redis


class EngineCache:
    """Redis cache and pub/sub hub for the Ascent engine.

    Three concerns:
      (a) Latest feed data (DataFrames serialized as JSON records)
      (b) Active trade/position state per strategy (group states)
      (c) Pub/sub event notifications (replaces Kafka)

    Key structure::

        ascent:feed:{feed_id}:latest         -> JSON (DataFrame records)
        ascent:feed:{feed_id}:updated_at     -> ISO timestamp string
        ascent:strategy:{strategy_id}:state  -> JSON {groups: {group_id: {state, trade, position}}}

    Pub/sub channels follow the pattern ``ascent.feed.{feed_id}``.

    Args:
        redis_url: Redis connection URL (e.g., ``redis://localhost:6379/0``).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    # ------------------------------------------------------------------
    # Feed cache
    # ------------------------------------------------------------------

    def set_feed_data(self, feed_id: uuid.UUID, df: pd.DataFrame, timestamp: str) -> None:
        """Cache the latest feed output DataFrame."""
        key = f"ascent:feed:{feed_id}:latest"
        ts_key = f"ascent:feed:{feed_id}:updated_at"
        data = df.to_json(orient="records", date_format="iso")
        pipe = self._redis.pipeline()
        pipe.set(key, data)
        pipe.set(ts_key, timestamp)
        pipe.execute()

    def get_feed_data(self, feed_id: uuid.UUID) -> pd.DataFrame | None:
        """Retrieve the latest cached feed data, or None if cold."""
        key = f"ascent:feed:{feed_id}:latest"
        data = self._redis.get(key)
        if data is None:
            return None
        records = json.loads(data)
        return pd.DataFrame(records)

    def get_all_feeds_data(self, feed_ids: list[uuid.UUID]) -> dict[uuid.UUID, pd.DataFrame | None]:
        """Retrieve latest data for multiple feeds (MGET)."""
        keys = [f"ascent:feed:{fid}:latest" for fid in feed_ids]
        values = self._redis.mget(keys)
        result: dict[uuid.UUID, pd.DataFrame | None] = {}
        for fid, raw in zip(feed_ids, values, strict=False):
            if raw is None:
                result[fid] = None
            else:
                result[fid] = pd.DataFrame(json.loads(raw))
        return result

    def is_cache_warm(self, feed_id: uuid.UUID) -> bool:
        """Check if a feed has cached data."""
        return self._redis.exists(f"ascent:feed:{feed_id}:latest") > 0

    # ------------------------------------------------------------------
    # Group state cache
    # ------------------------------------------------------------------

    def set_strategy_state(self, strategy_id: uuid.UUID, group_states: dict[str, Any]) -> None:
        """Atomically write strategy group states after evaluate()."""
        key = f"ascent:strategy:{strategy_id}:state"
        self._redis.set(key, json.dumps(group_states))

    def get_strategy_state(self, strategy_id: uuid.UUID) -> dict[str, Any] | None:
        """Retrieve strategy group states, or None if not cached."""
        key = f"ascent:strategy:{strategy_id}:state"
        data = self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Check Redis connectivity."""
        return self._redis.ping()

    # ------------------------------------------------------------------
    # Pub/sub (replaces Kafka)
    # ------------------------------------------------------------------

    def publish(self, channel: str, message: dict) -> None:
        """Publish a JSON event to a Redis pub/sub channel."""
        self._redis.publish(channel, json.dumps(message))

    def subscribe(self, channels: list[str]) -> redis.client.PubSub:
        """Subscribe to one or more Redis pub/sub channels.

        Returns a PubSub object. Callers should use :meth:`listen` to iterate
        over incoming messages, or use :meth:`poll` for timeout-based polling.
        """
        pubsub = self._redis.pubsub()
        pubsub.subscribe(*channels)
        return pubsub

    def poll(self, pubsub: redis.client.PubSub, timeout: float = 1.0) -> dict | None:
        """Poll for the next message on a PubSub subscription.

        Returns the parsed JSON payload, or None on timeout / non-message.
        """
        raw = pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        if raw is None or raw["type"] != "message":
            return None
        return json.loads(raw["data"])

"""HeartbeatService — periodic TTL refresh task.

A single background task owned by the Runner; refreshes the heartbeat key
for every registered entity every ``refresh_seconds``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from ascent.ports import HeartbeatStore

logger = logging.getLogger(__name__)


class HeartbeatService:
    def __init__(
        self,
        *,
        heartbeat_store: HeartbeatStore,
        targets: list[tuple[str, uuid.UUID]],
        refresh_seconds: float = 10.0,
        ttl_seconds: int = 30,
    ) -> None:
        self._store = heartbeat_store
        self._targets = list(targets)
        self._refresh = refresh_seconds
        self._ttl = ttl_seconds

    async def run_forever(self) -> None:
        try:
            while True:
                for entity_type, entity_id in self._targets:
                    await self._store.touch(entity_type, entity_id, ttl_seconds=self._ttl)
                await asyncio.sleep(self._refresh)
        except asyncio.CancelledError:
            logger.info("HeartbeatService cancelled")
            raise

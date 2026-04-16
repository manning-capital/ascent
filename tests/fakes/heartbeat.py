"""In-memory HeartbeatStore — tracks alive set; ignores TTLs (use FakeClock if needed)."""

from __future__ import annotations

import uuid

from ascent.ports import HeartbeatStore


class InMemoryHeartbeat(HeartbeatStore):
    def __init__(self) -> None:
        self._alive: set[tuple[str, uuid.UUID]] = set()
        self.touches: list[tuple[str, uuid.UUID, int]] = []

    async def touch(self, entity_type: str, entity_id: uuid.UUID, *, ttl_seconds: int = 30) -> None:
        self._alive.add((entity_type, entity_id))
        self.touches.append((entity_type, entity_id, ttl_seconds))

    async def is_alive(self, entity_type: str, entity_id: uuid.UUID) -> bool:
        return (entity_type, entity_id) in self._alive

    async def statuses(
        self, entity_type: str, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, bool]:
        return {eid: (entity_type, eid) in self._alive for eid in entity_ids}

    def expire(self, entity_type: str, entity_id: uuid.UUID) -> None:
        self._alive.discard((entity_type, entity_id))

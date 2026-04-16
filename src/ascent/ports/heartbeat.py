"""HeartbeatStore port — TTL-based liveness signal."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class HeartbeatStore(Protocol):
    async def touch(
        self, entity_type: str, entity_id: uuid.UUID, *, ttl_seconds: int = 30
    ) -> None: ...

    async def is_alive(self, entity_type: str, entity_id: uuid.UUID) -> bool: ...

    async def statuses(
        self, entity_type: str, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, bool]: ...

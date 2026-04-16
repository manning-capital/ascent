"""StateStore port — per-strategy KV state written after evaluate()."""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateStore(Protocol):
    async def get(self, strategy_id: uuid.UUID) -> dict[str, Any] | None: ...
    async def set(self, strategy_id: uuid.UUID, state: dict[str, Any]) -> None: ...

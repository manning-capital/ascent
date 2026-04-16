"""In-memory StateStore — dict keyed by strategy_id."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from ascent.ports import StateStore


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._state: dict[uuid.UUID, dict[str, Any]] = {}

    async def get(self, strategy_id: uuid.UUID) -> dict[str, Any] | None:
        value = self._state.get(strategy_id)
        return copy.deepcopy(value) if value is not None else None

    async def set(self, strategy_id: uuid.UUID, state: dict[str, Any]) -> None:
        self._state[strategy_id] = copy.deepcopy(state)

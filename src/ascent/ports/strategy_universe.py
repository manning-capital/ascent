"""Port for reading a strategy's active universe.

Returns the set of *active* scope IDs (instrument or composite) for a
strategy. The evaluator re-reads this on every tick so disable/enable
changes apply without a restart.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Protocol, runtime_checkable

Scope = Literal["instrument", "composite"]


@runtime_checkable
class StrategyUniverseRepository(Protocol):
    """Read-only access to a strategy's active scope.

    ``session`` is the opaque transactional handle from
    :class:`UnitOfWork.session`, mirroring :class:`TradeRepository`.
    """

    async def get_active_universe(
        self, session: Any, strategy_id: uuid.UUID, scope: Scope
    ) -> set[uuid.UUID]: ...

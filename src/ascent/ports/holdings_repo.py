"""HoldingsRepository — live, fill-driven view of per-strategy positions.

Reads return :class:`StrategyAssetHolding` domain types. Writes are atomic
``apply_delta`` UPSERTs keyed on
``(strategy_id, exchange_id, asset_id, position_type)``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from ascent.domain import PositionType, StrategyAssetHolding


@runtime_checkable
class HoldingsRepository(Protocol):
    async def get_for_strategy(
        self, session: Any, strategy_id: uuid.UUID
    ) -> list[StrategyAssetHolding]: ...

    async def apply_delta(
        self,
        session: Any,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        asset_id: uuid.UUID,
        position_type: PositionType,
        quantity_delta: Decimal,
        at: datetime,
    ) -> None:
        """UPSERT the holding row, applying ``quantity = quantity + delta``.

        Idempotency is the caller's concern — call this exactly once per
        fill. The repo unconditionally adds ``quantity_delta`` to whatever
        is on file.
        """
        ...

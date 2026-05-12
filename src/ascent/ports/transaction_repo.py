"""TransactionRepository — append-only journal for asset movements.

Each fill records one transaction row; together with the rolled-up
:class:`StrategyAssetHolding` rows this forms a double-entry view of a
strategy's positions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class NewTransactionSpec:
    """Args for :meth:`TransactionRepository.record`.

    ``strategy_id`` and ``trade_leg_id`` are nullable so non-fill-driven
    transactions (manual deposits, withdrawals) can also be recorded.
    Direction / position type is recovered via the leg when present.
    """

    timestamp: datetime
    transaction_type: str  # e.g. "BUY", "SELL", "DEPOSIT", "WITHDRAWAL"
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    quantity: float
    price: float
    strategy_id: uuid.UUID | None = None
    trade_leg_id: uuid.UUID | None = None
    fee_amount: float | None = None
    fee_asset_id: uuid.UUID | None = None


@runtime_checkable
class TransactionRepository(Protocol):
    async def record(self, session: Any, spec: NewTransactionSpec) -> uuid.UUID: ...

"""Per-strategy position-snapshot domain type.

Live counterpart to the :class:`StrategyAssetHolding` ORM row. The
:class:`HoldingsRepository` returns these. The :class:`PositionType` enum
lives in :mod:`ascent.domain.trade` and is reused here so the same enum
labels both a trade leg's direction and a holding's slot.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from ascent.domain.trade import PositionType


@dataclass(frozen=True)
class StrategyAssetHolding:
    strategy_id: uuid.UUID
    exchange_id: uuid.UUID
    asset_id: uuid.UUID
    asset_symbol: str | None
    position_type: PositionType
    quantity: float
    updated_at: datetime | None = None


__all__ = ["StrategyAssetHolding"]

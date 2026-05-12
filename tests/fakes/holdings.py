"""In-memory fakes for HoldingsRepository and TransactionRepository."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from ascent.domain import PositionType, StrategyAssetHolding
from ascent.ports import HoldingsRepository, NewTransactionSpec, TransactionRepository


@dataclass(frozen=True)
class _HoldingKey:
    strategy_id: uuid.UUID
    exchange_id: uuid.UUID
    asset_id: uuid.UUID
    position_type: PositionType


class InMemoryHoldingsRepository(HoldingsRepository):
    def __init__(self) -> None:
        self._rows: dict[_HoldingKey, dict] = {}
        self._asset_symbols: dict[uuid.UUID, str] = {}

    def register_asset_symbol(self, asset_id: uuid.UUID, symbol: str) -> None:
        """Test helper. Lets ``get_for_strategy`` return populated symbols."""
        self._asset_symbols[asset_id] = symbol

    async def get_for_strategy(
        self, session: Any, strategy_id: uuid.UUID
    ) -> list[StrategyAssetHolding]:
        return [
            StrategyAssetHolding(
                strategy_id=key.strategy_id,
                exchange_id=key.exchange_id,
                asset_id=key.asset_id,
                asset_symbol=self._asset_symbols.get(key.asset_id),
                position_type=key.position_type,
                quantity=row["quantity"],
                updated_at=row["updated_at"],
            )
            for key, row in self._rows.items()
            if key.strategy_id == strategy_id
        ]

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
        key = _HoldingKey(strategy_id, exchange_id, asset_id, position_type)
        existing = self._rows.get(key)
        if existing is None:
            self._rows[key] = {
                "quantity": float(quantity_delta),
                "updated_at": at,
            }
        else:
            existing["quantity"] = float(Decimal(str(existing["quantity"])) + quantity_delta)
            existing["updated_at"] = at

    # Test-only helpers

    def quantity_for(
        self,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        asset_id: uuid.UUID,
        position_type: PositionType,
    ) -> float:
        key = _HoldingKey(strategy_id, exchange_id, asset_id, position_type)
        row = self._rows.get(key)
        return row["quantity"] if row else 0.0


@dataclass
class InMemoryTransactionRepository(TransactionRepository):
    records: list[tuple[uuid.UUID, NewTransactionSpec]] = field(default_factory=list)

    async def record(self, session: Any, spec: NewTransactionSpec) -> uuid.UUID:
        tx_id = uuid.uuid4()
        self.records.append((tx_id, spec))
        return tx_id

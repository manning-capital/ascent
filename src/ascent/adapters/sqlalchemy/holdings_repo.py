"""SQLAlchemy adapter for :class:`ascent.ports.HoldingsRepository`."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models.assets import Asset
from ascent.database.models.strategy_asset_holding import StrategyAssetHolding as HoldingRow
from ascent.domain import PositionType, StrategyAssetHolding
from ascent.ports import HoldingsRepository


class SqlAlchemyHoldingsRepository(HoldingsRepository):
    async def get_for_strategy(
        self, session: Session, strategy_id: uuid.UUID
    ) -> list[StrategyAssetHolding]:
        return await asyncio.to_thread(self._get_for_strategy_sync, session, strategy_id)

    async def apply_delta(
        self,
        session: Session,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        asset_id: uuid.UUID,
        position_type: PositionType,
        quantity_delta: Decimal,
        at: datetime,
    ) -> None:
        await asyncio.to_thread(
            self._apply_delta_sync,
            session,
            strategy_id,
            exchange_id,
            asset_id,
            position_type,
            quantity_delta,
            at,
        )

    # ---------------- sync internals ----------------

    @staticmethod
    def _get_for_strategy_sync(db: Session, strategy_id: uuid.UUID) -> list[StrategyAssetHolding]:
        rows = db.execute(
            select(HoldingRow, Asset.name)
            .join(Asset, Asset.id == HoldingRow.asset_id)
            .where(HoldingRow.strategy_id == strategy_id)
        ).all()
        return [
            StrategyAssetHolding(
                strategy_id=row.strategy_id,
                exchange_id=row.exchange_id,
                asset_id=row.asset_id,
                asset_symbol=asset_name,
                position_type=PositionType(row.position_type),
                quantity=float(row.quantity),
                updated_at=row.updated_at,
            )
            for row, asset_name in rows
        ]

    @staticmethod
    def _apply_delta_sync(
        db: Session,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        asset_id: uuid.UUID,
        position_type: PositionType,
        quantity_delta: Decimal,
        at: datetime,
    ) -> None:
        existing = db.execute(
            select(HoldingRow).where(
                HoldingRow.strategy_id == strategy_id,
                HoldingRow.exchange_id == exchange_id,
                HoldingRow.asset_id == asset_id,
                HoldingRow.position_type == position_type.value,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                HoldingRow(
                    strategy_id=strategy_id,
                    exchange_id=exchange_id,
                    asset_id=asset_id,
                    position_type=position_type.value,
                    quantity=float(quantity_delta),
                    updated_at=at,
                )
            )
        else:
            existing.quantity = float(Decimal(str(existing.quantity)) + quantity_delta)
            existing.updated_at = at
        db.flush()

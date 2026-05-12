"""SQLAlchemy adapter for :class:`ascent.ports.TransactionRepository`."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.orm import Session

from ascent.adapters.sqlalchemy.type_cache import TypeCache
from ascent.database.models.transactions import Transaction as TransactionRow
from ascent.ports import NewTransactionSpec, TransactionRepository


class SqlAlchemyTransactionRepository(TransactionRepository):
    def __init__(self, types: TypeCache) -> None:
        self._types = types

    async def record(self, session: Session, spec: NewTransactionSpec) -> uuid.UUID:
        return await asyncio.to_thread(self._record_sync, session, spec)

    def _record_sync(self, db: Session, spec: NewTransactionSpec) -> uuid.UUID:
        row = TransactionRow(
            timestamp=spec.timestamp,
            transaction_type_id=self._types.transaction_type_id(spec.transaction_type),
            strategy_id=spec.strategy_id,
            trade_leg_id=spec.trade_leg_id,
            from_asset_id=spec.from_asset_id,
            to_asset_id=spec.to_asset_id,
            quantity=spec.quantity,
            price=spec.price,
            fee_amount=spec.fee_amount,
            fee_asset_id=spec.fee_asset_id,
        )
        db.add(row)
        db.flush()
        return row.id

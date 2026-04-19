"""SQLAlchemy adapter for :class:`ascent.ports.TradeRepository`.

Every method takes a ``Session`` from the enclosing :class:`UnitOfWork`
and mutates it. This adapter never commits — the UoW owns that.

The sync work happens on a thread pool (``asyncio.to_thread``) so we keep
the async port contract without migrating to async SQLAlchemy. SA Sessions
are not thread-safe for *concurrent* use; since awaits serialize the
``to_thread`` calls on a given session, sequential use across threads is
safe.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.adapters.sqlalchemy.mappers import OrmMappers
from ascent.adapters.sqlalchemy.type_cache import TypeCache
from ascent.database.models.trades import Trade as TradeRow
from ascent.database.models.trades import TradeLeg as TradeLegRow
from ascent.database.models.trades import TradeStatus as TradeStatusRow
from ascent.domain import Trade, TradeState
from ascent.ports import TradeRepository
from ascent.ports.trade_repo import NewLegSpec


class SqlAlchemyTradeRepository(TradeRepository):
    def __init__(self, types: TypeCache, mappers: OrmMappers) -> None:
        self._types = types
        self._mappers = mappers

    async def get(self, session: Session, trade_id: uuid.UUID) -> Trade | None:
        return await asyncio.to_thread(self._get_sync, session, trade_id)

    async def list_non_terminal_for_strategy(
        self, session: Session, strategy_id: uuid.UUID
    ) -> list[Trade]:
        return await asyncio.to_thread(self._list_non_terminal_sync, session, strategy_id)

    async def list_open_for_strategy(self, session: Session, strategy_id: uuid.UUID) -> list[Trade]:
        return await asyncio.to_thread(self._list_open_sync, session, strategy_id)

    async def create(
        self,
        session: Session,
        *,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        is_paper: bool,
        entry_at: datetime,
        strategy_run_id: uuid.UUID | None,
        legs: list[NewLegSpec],
    ) -> Trade:
        return await asyncio.to_thread(
            self._create_sync,
            session,
            strategy_id,
            portfolio_id,
            is_paper,
            entry_at,
            strategy_run_id,
            legs,
        )

    async def set_state(
        self,
        session: Session,
        trade_id: uuid.UUID,
        *,
        new_state: TradeState,
        at: datetime,
        exit_at: datetime | None = None,
        total_realized_pnl: float | None = None,
        close_reason: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._set_state_sync,
            session,
            trade_id,
            new_state,
            at,
            exit_at,
            total_realized_pnl,
            close_reason,
        )

    async def set_leg_prices(
        self,
        session: Session,
        leg_id: uuid.UUID,
        *,
        entry_price: float | None = None,
        exit_price: float | None = None,
        realized_pnl: float | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._set_leg_prices_sync, session, leg_id, entry_price, exit_price, realized_pnl
        )

    async def set_entry_order(
        self, session: Session, leg_id: uuid.UUID, order_id: uuid.UUID
    ) -> None:
        await asyncio.to_thread(self._set_entry_order_sync, session, leg_id, order_id)

    async def set_exit_order(
        self, session: Session, leg_id: uuid.UUID, order_id: uuid.UUID
    ) -> None:
        await asyncio.to_thread(self._set_exit_order_sync, session, leg_id, order_id)

    # ---------------- sync internals (operate on the caller's session) ----------------

    def _get_sync(self, db: Session, trade_id: uuid.UUID) -> Trade | None:
        row = db.get(TradeRow, trade_id)
        return None if row is None else self._mappers.trade_from_row(row, db)

    def _list_non_terminal_sync(self, db: Session, strategy_id: uuid.UUID) -> list[Trade]:
        terminal_ids = [
            self._types.trade_state_id(s)
            for s in (TradeState.CLOSED, TradeState.CANCELLED)
            if s in self._types._trade_state_to_id
        ]
        stmt = select(TradeRow).where(TradeRow.strategy_id == strategy_id)
        if terminal_ids:
            stmt = stmt.where(TradeRow.current_status_type_id.notin_(terminal_ids))
        rows = db.execute(stmt).scalars().all()
        return [self._mappers.trade_from_row(r, db) for r in rows]

    def _list_open_sync(self, db: Session, strategy_id: uuid.UUID) -> list[Trade]:
        open_id = self._types.trade_state_id(TradeState.OPEN)
        rows = (
            db.execute(
                select(TradeRow).where(
                    TradeRow.strategy_id == strategy_id,
                    TradeRow.current_status_type_id == open_id,
                )
            )
            .scalars()
            .all()
        )
        return [self._mappers.trade_from_row(r, db) for r in rows]

    def _create_sync(
        self,
        db: Session,
        strategy_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        is_paper: bool,
        entry_at: datetime,
        strategy_run_id: uuid.UUID | None,
        legs: list[NewLegSpec],
    ) -> Trade:
        pending_id = self._types.trade_state_id(TradeState.PENDING)
        trade = TradeRow(
            strategy_id=strategy_id,
            strategy_run_id=strategy_run_id,
            portfolio_id=portfolio_id,
            is_paper=is_paper,
            entry_at=entry_at,
            current_status_type_id=pending_id,
        )
        db.add(trade)
        db.flush()
        db.add(
            TradeStatusRow(
                timestamp=entry_at,
                trade_id=trade.id,
                trade_status_type_id=pending_id,
            )
        )
        for spec in legs:
            db.add(
                TradeLegRow(
                    trade_id=trade.id,
                    instrument_id=spec.instrument_id,
                    direction=spec.direction.value,
                    quantity=spec.quantity,
                    expected_entry_price=spec.expected_entry_price,
                    exchange_id=spec.exchange_id,
                )
            )
        db.flush()
        return self._mappers.trade_from_row(trade, db)

    def _set_state_sync(
        self,
        db: Session,
        trade_id: uuid.UUID,
        new_state: TradeState,
        at: datetime,
        exit_at: datetime | None,
        total_realized_pnl: float | None,
        close_reason: str | None,
    ) -> None:
        status_id = self._types.trade_state_id(new_state)
        trade = db.get(TradeRow, trade_id)
        if trade is None:
            return
        trade.current_status_type_id = status_id
        if exit_at is not None:
            trade.exit_at = exit_at
        if total_realized_pnl is not None:
            trade.total_realized_pnl = total_realized_pnl
        if close_reason is not None:
            trade.close_reason = close_reason
        # Collision guard: status_history is PK on (trade_id, timestamp), so if
        # two transitions land in the same microsecond we nudge the second.
        timestamp = at
        last = (
            db.execute(
                select(TradeStatusRow)
                .where(TradeStatusRow.trade_id == trade_id)
                .order_by(TradeStatusRow.timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if last is not None and last.timestamp >= timestamp:
            timestamp = last.timestamp + timedelta(microseconds=1)
        db.add(
            TradeStatusRow(
                timestamp=timestamp,
                trade_id=trade_id,
                trade_status_type_id=status_id,
            )
        )
        db.flush()

    def _set_leg_prices_sync(
        self,
        db: Session,
        leg_id: uuid.UUID,
        entry_price: float | None,
        exit_price: float | None,
        realized_pnl: float | None,
    ) -> None:
        leg = db.get(TradeLegRow, leg_id)
        if leg is None:
            return
        if entry_price is not None:
            leg.entry_price = entry_price
        if exit_price is not None:
            leg.exit_price = exit_price
        if realized_pnl is not None:
            leg.realized_pnl = realized_pnl
        db.flush()

    def _set_entry_order_sync(self, db: Session, leg_id: uuid.UUID, order_id: uuid.UUID) -> None:
        leg = db.get(TradeLegRow, leg_id)
        if leg is None:
            return
        leg.entry_order_id = order_id
        db.flush()

    def _set_exit_order_sync(self, db: Session, leg_id: uuid.UUID, order_id: uuid.UUID) -> None:
        leg = db.get(TradeLegRow, leg_id)
        if leg is None:
            return
        leg.exit_order_id = order_id
        db.flush()

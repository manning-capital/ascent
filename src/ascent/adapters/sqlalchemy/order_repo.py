"""SQLAlchemy adapter for :class:`ascent.ports.OrderRepository`."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.adapters.sqlalchemy.mappers import OrmMappers
from ascent.adapters.sqlalchemy.type_cache import TypeCache
from ascent.database.models.orders import Order as OrderRow
from ascent.database.models.orders import OrderStatus as OrderStatusRow
from ascent.database.models.trades import Trade as TradeRow
from ascent.database.models.trades import TradeLeg as TradeLegRow
from ascent.domain import Order, OrderState, TradeState
from ascent.ports import OrderRepository
from ascent.ports.trade_repo import NewOrderSpec


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(
        self, session_factory: sessionmaker, types: TypeCache, mappers: OrmMappers
    ) -> None:
        self._sf = session_factory
        self._types = types
        self._mappers = mappers

    async def get(self, order_id: uuid.UUID) -> Order | None:
        return await asyncio.to_thread(self._get_sync, order_id)

    async def list_for_exchange(
        self, exchange_id: uuid.UUID, *, only_non_terminal_trades: bool = True
    ) -> list[tuple[Order, uuid.UUID, uuid.UUID]]:
        return await asyncio.to_thread(self._list_sync, exchange_id, only_non_terminal_trades)

    async def create(self, spec: NewOrderSpec) -> Order:
        return await asyncio.to_thread(self._create_sync, spec)

    async def record_status(
        self,
        order_id: uuid.UUID,
        *,
        new_state: OrderState,
        at: datetime,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._record_status_sync, order_id, new_state, at, error_message, error_code
        )

    async def set_external_id(self, order_id: uuid.UUID, external_order_id: str) -> None:
        await asyncio.to_thread(self._set_external_id_sync, order_id, external_order_id)

    async def set_fill(
        self,
        order_id: uuid.UUID,
        *,
        filled_quantity: float,
        average_fill_price: float | None,
    ) -> None:
        await asyncio.to_thread(self._set_fill_sync, order_id, filled_quantity, average_fill_price)

    # ---------------- sync internals ----------------

    def _get_sync(self, order_id: uuid.UUID) -> Order | None:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = db.get(OrderRow, order_id)
            return None if row is None else self._mappers.order_from_row(row, db)

    def _list_sync(
        self, exchange_id: uuid.UUID, only_non_terminal_trades: bool
    ) -> list[tuple[Order, uuid.UUID, uuid.UUID]]:
        terminal_ids = (
            [
                self._types.trade_state_id(s)
                for s in (TradeState.CLOSED, TradeState.CANCELLED)
                if s in self._types._trade_state_to_id
            ]
            if only_non_terminal_trades
            else []
        )
        with Session(bind=self._sf.kw["bind"]) as db:
            rows = (
                db.execute(
                    select(OrderRow)
                    .where(OrderRow.exchange_id == exchange_id)
                    .where(OrderRow.trade_leg_id.isnot(None))
                )
                .scalars()
                .all()
            )
            out: list[tuple[Order, uuid.UUID, uuid.UUID]] = []
            for row in rows:
                leg = db.get(TradeLegRow, row.trade_leg_id)
                if leg is None:
                    continue
                trade = db.get(TradeRow, leg.trade_id)
                if trade is None:
                    continue
                if terminal_ids and trade.current_status_type_id in terminal_ids:
                    continue
                out.append((self._mappers.order_from_row(row, db), leg.id, trade.id))
            return out

    def _create_sync(self, spec: NewOrderSpec) -> Order:
        with Session(bind=self._sf.kw["bind"]) as db:
            row = OrderRow(
                timestamp=spec.timestamp,
                order_type_id=self._types.order_type_id(spec.order_type),
                side=spec.side,
                exchange_id=spec.exchange_id,
                portfolio_id=spec.portfolio_id,
                instrument_id=spec.instrument_id,
                quantity=spec.quantity,
                price=spec.price,
                trade_leg_id=spec.trade_leg_id,
            )
            db.add(row)
            db.flush()
            db.add(
                OrderStatusRow(
                    timestamp=spec.timestamp,
                    order_id=row.id,
                    order_status_type_id=self._types.order_state_id(OrderState.SUBMITTED),
                )
            )
            db.commit()
            return self._mappers.order_from_row(row, db)

    def _record_status_sync(
        self,
        order_id: uuid.UUID,
        new_state: OrderState,
        at: datetime,
        error_message: str | None,
        error_code: str | None,
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            db.add(
                OrderStatusRow(
                    timestamp=at,
                    order_id=order_id,
                    order_status_type_id=self._types.order_state_id(new_state),
                    error_message=error_message,
                    error_code=error_code,
                )
            )
            db.commit()

    def _set_external_id_sync(self, order_id: uuid.UUID, external_order_id: str) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            order = db.get(OrderRow, order_id)
            if order and not order.external_order_id:
                order.external_order_id = external_order_id
                db.commit()

    def _set_fill_sync(
        self, order_id: uuid.UUID, filled_quantity: float, average_fill_price: float | None
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            order = db.get(OrderRow, order_id)
            if order is None:
                return
            if filled_quantity is not None:
                order.filled_quantity = filled_quantity
            if average_fill_price is not None:
                order.average_fill_price = average_fill_price
            db.commit()

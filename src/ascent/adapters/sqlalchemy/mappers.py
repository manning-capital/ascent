"""ORM ↔ domain type translation. Lives at the SQLAlchemy adapter boundary."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.adapters.sqlalchemy.type_cache import TypeCache
from ascent.database.models.instruments import Instrument as InstrumentRow
from ascent.database.models.orders import Order as OrderRow
from ascent.database.models.orders import OrderStatus as OrderStatusRow
from ascent.database.models.trades import Trade as TradeRow
from ascent.database.models.trades import TradeLeg as TradeLegRow
from ascent.domain import (
    Order,
    OrderSide,
    OrderState,
    PositionType,
    Trade,
    TradeLeg,
    TradeState,
)


class OrmMappers:
    def __init__(self, types: TypeCache) -> None:
        self._types = types

    # -------- Orders --------

    def order_from_row(self, row: OrderRow, db: Session) -> Order:
        latest = (
            db.execute(
                select(OrderStatusRow)
                .where(OrderStatusRow.order_id == row.id)
                .order_by(OrderStatusRow.timestamp.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        state = (
            self._types.order_state_for_id(latest.order_status_type_id)
            if latest
            else OrderState.SUBMITTED
        ) or OrderState.SUBMITTED
        return Order(
            id=row.id,
            state=state,
            side=OrderSide(row.side),
            instrument_id=row.instrument_id,
            quantity=row.quantity,
            price=row.price,
            filled_quantity=row.filled_quantity or 0.0,
            average_fill_price=row.average_fill_price,
            external_order_id=row.external_order_id,
            error_message=(latest.error_message if latest else None),
        )

    # -------- Trades --------

    def trade_from_row(self, row: TradeRow, db: Session) -> Trade:
        leg_rows = (
            db.execute(select(TradeLegRow).where(TradeLegRow.trade_id == row.id)).scalars().all()
        )
        legs = tuple(self._leg_from_row(leg, db) for leg in leg_rows)
        state = self._types.trade_state_for_id(row.current_status_type_id) or TradeState.PENDING
        return Trade(
            id=row.id,
            strategy_id=row.strategy_id,
            state=state,
            is_paper=row.is_paper,
            legs=legs,
            entry_at=row.entry_at,
            exit_at=row.exit_at,
            total_realized_pnl=row.total_realized_pnl,
            strategy_run_id=row.strategy_run_id,
            composite_id=row.composite_id,
        )

    def _leg_from_row(self, row: TradeLegRow, db: Session) -> TradeLeg:
        entry_order = (
            self.order_from_row(db.get(OrderRow, row.entry_order_id), db)
            if row.entry_order_id
            else None
        )
        exit_order = (
            self.order_from_row(db.get(OrderRow, row.exit_order_id), db)
            if row.exit_order_id
            else None
        )
        from_asset_symbol, to_asset_symbol = self._asset_symbols_for_instrument(
            db, row.instrument_id
        )
        return TradeLeg(
            id=row.id,
            instrument_id=row.instrument_id,
            direction=PositionType(row.direction),
            quantity=row.quantity,
            entry_order=entry_order,
            exit_order=exit_order,
            entry_price=row.entry_price,
            exit_price=row.exit_price,
            realized_pnl=row.realized_pnl,
            from_asset_symbol=from_asset_symbol,
            to_asset_symbol=to_asset_symbol,
            exchange_id=row.exchange_id,
        )

    @staticmethod
    def _asset_symbols_for_instrument(db: Session, instrument_id) -> tuple[str | None, str | None]:
        """Look up base/quote asset symbols for an instrument.

        Reads the instrument row with its ``from_asset`` / ``to_asset``
        relationships. SQLAlchemy lazy-loads these the first time per row;
        for batch reads (the reconciliation sweep) the cost is one extra
        query per distinct instrument, which is acceptable for the sweep's
        size — and the alternative (eager-loading every leg query) would
        slow the hot path of single-trade reads.
        """
        row = db.get(InstrumentRow, instrument_id)
        if row is None:
            return (None, None)
        from_name = row.from_asset.name if row.from_asset is not None else None
        to_name = row.to_asset.name if row.to_asset is not None else None
        return (from_name, to_name)

    # -------- Simple utilities --------

    @staticmethod
    def order_id_terminal(state: OrderState) -> bool:
        return state.is_terminal

    @staticmethod
    def trade_id_terminal(state: TradeState) -> bool:
        return state.is_terminal

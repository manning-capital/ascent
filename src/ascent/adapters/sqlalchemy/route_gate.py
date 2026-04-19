"""SQLAlchemy adapter for :class:`ascent.ports.RouteGate`.

Re-queries on every ``submit()`` call. Submits are rare relative to
strategy evaluation ticks, so we avoid an in-memory cache: a fresh read
guarantees disable/pause edits made through the impact-check endpoints
take effect on the very next trade attempt with no invalidation plumbing.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import StrategyExchange
from ascent.database.models.exchanges import Exchange
from ascent.database.models.instruments import Instrument
from ascent.database.models.strategy import Strategy
from ascent.ports import RouteGate


class SqlAlchemyRouteGate(RouteGate):
    async def validate_open(
        self,
        session: Session,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        instrument_ids: list[uuid.UUID],
    ) -> str | None:
        return await asyncio.to_thread(
            self._validate_sync, session, strategy_id, exchange_id, instrument_ids
        )

    def _validate_sync(
        self,
        db: Session,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        instrument_ids: list[uuid.UUID],
    ) -> str | None:
        strategy = db.get(Strategy, strategy_id)
        if strategy is not None and strategy.is_paused:
            return "strategy_paused"

        sx = db.get(StrategyExchange, (strategy_id, exchange_id))
        if sx is None:
            return "assignment_missing"
        if not sx.is_active:
            return "assignment_disabled"

        exchange = db.get(Exchange, exchange_id)
        if exchange is None:
            return "exchange_missing"

        rows = db.execute(
            select(
                Instrument.id, Instrument.provider_id, Instrument.instrument_type_id
            ).where(Instrument.id.in_(instrument_ids))
        ).all()
        found_ids = {r.id for r in rows}
        if found_ids != set(instrument_ids):
            return "instrument_missing"

        for row in rows:
            if (row.provider_id, row.instrument_type_id) != (
                exchange.provider_id,
                exchange.instrument_type_id,
            ):
                return "provider_mismatch"

        return None

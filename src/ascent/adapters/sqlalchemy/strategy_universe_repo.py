"""SQLAlchemy adapter for :class:`ascent.ports.StrategyUniverseRepository`.

Returns the currently-active subset of ``StrategyInstrumentScope`` /
``StrategyCompositeScope`` rows. The bitemporal scope tables encode "active"
as ``dropped_at IS NULL``; the partial unique index keeps this query fast.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import StrategyCompositeScope, StrategyInstrumentScope
from ascent.ports import StrategyUniverseRepository
from ascent.ports.strategy_universe import Scope


class SqlAlchemyStrategyUniverseRepository(StrategyUniverseRepository):
    async def get_active_universe(
        self, session: Session, strategy_id: uuid.UUID, scope: Scope
    ) -> set[uuid.UUID]:
        return await asyncio.to_thread(self._get_sync, session, strategy_id, scope)

    def _get_sync(
        self, db: Session, strategy_id: uuid.UUID, scope: Scope
    ) -> set[uuid.UUID]:
        if scope == "composite":
            rows = db.execute(
                select(StrategyCompositeScope.composite_id)
                .where(StrategyCompositeScope.strategy_id == strategy_id)
                .where(StrategyCompositeScope.dropped_at.is_(None))
            ).all()
        else:
            rows = db.execute(
                select(StrategyInstrumentScope.instrument_id)
                .where(StrategyInstrumentScope.strategy_id == strategy_id)
                .where(StrategyInstrumentScope.dropped_at.is_(None))
            ).all()
        return {r[0] for r in rows}

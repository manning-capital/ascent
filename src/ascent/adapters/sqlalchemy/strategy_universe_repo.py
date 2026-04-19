"""SQLAlchemy adapter for :class:`ascent.ports.StrategyUniverseRepository`.

Returns the active subset of ``StrategyInstrumentScope`` /
``StrategyCompositeScope`` rows. The query is intentionally tiny — a single
indexed lookup on ``strategy_id`` filtered by ``is_active=True`` — so we can
re-read it on every evaluation tick without measurable overhead.
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
                .where(StrategyCompositeScope.is_active.is_(True))
            ).all()
        else:
            rows = db.execute(
                select(StrategyInstrumentScope.instrument_id)
                .where(StrategyInstrumentScope.strategy_id == strategy_id)
                .where(StrategyInstrumentScope.is_active.is_(True))
            ).all()
        return {r[0] for r in rows}

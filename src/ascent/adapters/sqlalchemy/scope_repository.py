"""SQLAlchemy adapter for :class:`ascent.ports.ScopeRepository`.

Bitemporal chokepoint over the four scope tables. Every read and edit goes
through this adapter; application code never touches `is_active`-style
boolean filters or raw inserts.

Reads:
  - `_as_of` returns rows whose interval `[added_at, dropped_at)` covers
    the given timestamp. `dropped_at IS NULL` means "still active."
  - `_active` is the special case `_as_of(now)` and uses the partial unique
    index for a tighter plan.

Writes:
  - `add_*` is idempotent: re-adding an already-active row is a no-op.
    Otherwise inserts a new row with `added_at=at`.
  - `drop_*` is idempotent: dropping an already-dropped row is a no-op.
    Otherwise sets `dropped_at=at` on the active row.
  - `drop_all_*_memberships` cascades a parent-entity delete by soft-dropping
    all active rows referencing it.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models import (
    FeedCompositeScope,
    FeedInstrumentScope,
    StrategyCompositeScope,
    StrategyInstrumentScope,
)
from ascent.ports import ScopeMembershipRecord, ScopeRepository


class SqlAlchemyScopeRepository(ScopeRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    # --- as-of reads ---

    async def get_feed_instruments_as_of(
        self, feed_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_as_of_sync,
            FeedInstrumentScope,
            "feed_id",
            feed_id,
            "instrument_id",
            as_of,
        )

    async def get_feed_composites_as_of(
        self, feed_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_as_of_sync,
            FeedCompositeScope,
            "feed_id",
            feed_id,
            "composite_id",
            as_of,
        )

    async def get_strategy_instruments_as_of(
        self, strategy_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_as_of_sync,
            StrategyInstrumentScope,
            "strategy_id",
            strategy_id,
            "instrument_id",
            as_of,
        )

    async def get_strategy_composites_as_of(
        self, strategy_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_as_of_sync,
            StrategyCompositeScope,
            "strategy_id",
            strategy_id,
            "composite_id",
            as_of,
        )

    # --- current-state reads ---

    async def get_feed_instruments_active(self, feed_id: uuid.UUID) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_active_sync,
            FeedInstrumentScope,
            "feed_id",
            feed_id,
            "instrument_id",
        )

    async def get_feed_composites_active(self, feed_id: uuid.UUID) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_active_sync,
            FeedCompositeScope,
            "feed_id",
            feed_id,
            "composite_id",
        )

    async def get_strategy_instruments_active(self, strategy_id: uuid.UUID) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_active_sync,
            StrategyInstrumentScope,
            "strategy_id",
            strategy_id,
            "instrument_id",
        )

    async def get_strategy_composites_active(self, strategy_id: uuid.UUID) -> list[uuid.UUID]:
        return await asyncio.to_thread(
            self._members_active_sync,
            StrategyCompositeScope,
            "strategy_id",
            strategy_id,
            "composite_id",
        )

    # --- edits: add ---

    async def add_feed_instrument(
        self,
        feed_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None:
        await asyncio.to_thread(
            self._add_sync,
            FeedInstrumentScope,
            "feed_id",
            feed_id,
            "instrument_id",
            instrument_id,
            at,
            order,
        )

    async def add_feed_composite(
        self,
        feed_id: uuid.UUID,
        composite_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None:
        await asyncio.to_thread(
            self._add_sync,
            FeedCompositeScope,
            "feed_id",
            feed_id,
            "composite_id",
            composite_id,
            at,
            order,
        )

    async def add_strategy_instrument(
        self,
        strategy_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None:
        await asyncio.to_thread(
            self._add_sync,
            StrategyInstrumentScope,
            "strategy_id",
            strategy_id,
            "instrument_id",
            instrument_id,
            at,
            order,
        )

    async def add_strategy_composite(
        self,
        strategy_id: uuid.UUID,
        composite_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None:
        await asyncio.to_thread(
            self._add_sync,
            StrategyCompositeScope,
            "strategy_id",
            strategy_id,
            "composite_id",
            composite_id,
            at,
            order,
        )

    # --- edits: drop ---

    async def drop_feed_instrument(
        self, feed_id: uuid.UUID, instrument_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_sync,
            FeedInstrumentScope,
            "feed_id",
            feed_id,
            "instrument_id",
            instrument_id,
            at,
        )

    async def drop_feed_composite(
        self, feed_id: uuid.UUID, composite_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_sync,
            FeedCompositeScope,
            "feed_id",
            feed_id,
            "composite_id",
            composite_id,
            at,
        )

    async def drop_strategy_instrument(
        self, strategy_id: uuid.UUID, instrument_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_sync,
            StrategyInstrumentScope,
            "strategy_id",
            strategy_id,
            "instrument_id",
            instrument_id,
            at,
        )

    async def drop_strategy_composite(
        self, strategy_id: uuid.UUID, composite_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_sync,
            StrategyCompositeScope,
            "strategy_id",
            strategy_id,
            "composite_id",
            composite_id,
            at,
        )

    # --- soft-cascade ---

    async def drop_all_feed_memberships(self, feed_id: uuid.UUID, *, at: datetime) -> None:
        await asyncio.to_thread(
            self._drop_all_sync,
            [(FeedInstrumentScope, "feed_id"), (FeedCompositeScope, "feed_id")],
            feed_id,
            at,
        )

    async def drop_all_strategy_memberships(self, strategy_id: uuid.UUID, *, at: datetime) -> None:
        await asyncio.to_thread(
            self._drop_all_sync,
            [
                (StrategyInstrumentScope, "strategy_id"),
                (StrategyCompositeScope, "strategy_id"),
            ],
            strategy_id,
            at,
        )

    async def drop_all_instrument_memberships(
        self, instrument_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_all_sync,
            [
                (FeedInstrumentScope, "instrument_id"),
                (StrategyInstrumentScope, "instrument_id"),
            ],
            instrument_id,
            at,
        )

    async def drop_all_composite_memberships(
        self, composite_id: uuid.UUID, *, at: datetime
    ) -> None:
        await asyncio.to_thread(
            self._drop_all_sync,
            [
                (FeedCompositeScope, "composite_id"),
                (StrategyCompositeScope, "composite_id"),
            ],
            composite_id,
            at,
        )

    # --- range queries ---

    async def get_feed_instruments_active_during(
        self, feed_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]:
        return await asyncio.to_thread(
            self._range_sync,
            FeedInstrumentScope,
            "feed_id",
            feed_id,
            "instrument_id",
            start,
            end,
        )

    async def get_feed_composites_active_during(
        self, feed_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]:
        return await asyncio.to_thread(
            self._range_sync,
            FeedCompositeScope,
            "feed_id",
            feed_id,
            "composite_id",
            start,
            end,
        )

    async def get_strategy_instruments_active_during(
        self, strategy_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]:
        return await asyncio.to_thread(
            self._range_sync,
            StrategyInstrumentScope,
            "strategy_id",
            strategy_id,
            "instrument_id",
            start,
            end,
        )

    async def get_strategy_composites_active_during(
        self, strategy_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]:
        return await asyncio.to_thread(
            self._range_sync,
            StrategyCompositeScope,
            "strategy_id",
            strategy_id,
            "composite_id",
            start,
            end,
        )

    # --- sync helpers ---

    def _members_as_of_sync(
        self,
        model: Any,
        parent_col: str,
        parent_id: uuid.UUID,
        member_col: str,
        as_of: datetime,
    ) -> list[uuid.UUID]:
        member = getattr(model, member_col)
        with Session(bind=self._sf.kw["bind"]) as db:
            rows = db.execute(
                select(member)
                .where(getattr(model, parent_col) == parent_id)
                .where(model.added_at <= as_of)
                .where(or_(model.dropped_at.is_(None), model.dropped_at > as_of))
                .order_by(model.order)
            ).all()
        return [r[0] for r in rows]

    def _members_active_sync(
        self,
        model: Any,
        parent_col: str,
        parent_id: uuid.UUID,
        member_col: str,
    ) -> list[uuid.UUID]:
        member = getattr(model, member_col)
        with Session(bind=self._sf.kw["bind"]) as db:
            rows = db.execute(
                select(member)
                .where(getattr(model, parent_col) == parent_id)
                .where(model.dropped_at.is_(None))
                .order_by(model.order)
            ).all()
        return [r[0] for r in rows]

    def _add_sync(
        self,
        model: Any,
        parent_col: str,
        parent_id: uuid.UUID,
        member_col: str,
        member_id: uuid.UUID,
        at: datetime,
        order: int,
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            existing = db.execute(
                select(model)
                .where(getattr(model, parent_col) == parent_id)
                .where(getattr(model, member_col) == member_id)
                .where(model.dropped_at.is_(None))
            ).scalar_one_or_none()
            if existing is not None:
                return
            row = model(
                **{parent_col: parent_id, member_col: member_id},
                order=order,
                added_at=at,
            )
            db.add(row)
            db.commit()

    def _drop_sync(
        self,
        model: Any,
        parent_col: str,
        parent_id: uuid.UUID,
        member_col: str,
        member_id: uuid.UUID,
        at: datetime,
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            db.execute(
                update(model)
                .where(getattr(model, parent_col) == parent_id)
                .where(getattr(model, member_col) == member_id)
                .where(model.dropped_at.is_(None))
                .values(dropped_at=at)
            )
            db.commit()

    def _drop_all_sync(
        self,
        targets: list[tuple[Any, str]],
        parent_id: uuid.UUID,
        at: datetime,
    ) -> None:
        with Session(bind=self._sf.kw["bind"]) as db:
            for model, parent_col in targets:
                db.execute(
                    update(model)
                    .where(getattr(model, parent_col) == parent_id)
                    .where(model.dropped_at.is_(None))
                    .values(dropped_at=at)
                )
            db.commit()

    def _range_sync(
        self,
        model: Any,
        parent_col: str,
        parent_id: uuid.UUID,
        member_col: str,
        start: datetime,
        end: datetime,
    ) -> list[ScopeMembershipRecord]:
        member = getattr(model, member_col)
        with Session(bind=self._sf.kw["bind"]) as db:
            rows = db.execute(
                select(member, model.added_at, model.dropped_at)
                .where(getattr(model, parent_col) == parent_id)
                .where(
                    and_(
                        model.added_at < end,
                        or_(model.dropped_at.is_(None), model.dropped_at > start),
                    )
                )
                .order_by(model.added_at)
            ).all()
        return [
            ScopeMembershipRecord(
                scope_id=parent_id,
                member_id=r[0],
                added_at=r[1],
                dropped_at=r[2],
            )
            for r in rows
        ]

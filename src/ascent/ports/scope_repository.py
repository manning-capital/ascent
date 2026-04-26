"""Port for reading and editing the four bitemporal scope tables.

Single chokepoint over `feed_instrument_scope`, `feed_composite_scope`,
`strategy_instrument_scope`, `strategy_composite_scope`. Application code
never touches these tables directly — every read and every edit goes
through this protocol so that membership history is faithfully recorded
and reconstructable.

`add` and `drop` accept an explicit `at` timestamp; the caller decides the
effective time. In normal operation it's `datetime.now(UTC)`; in tests and
seeds it can be set explicitly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ScopeMembershipRecord:
    """One historical interval of a scope membership."""

    scope_id: uuid.UUID  # the parent (feed_id or strategy_id)
    member_id: uuid.UUID  # the child (instrument_id or composite_id)
    added_at: datetime
    dropped_at: datetime | None  # None == still active


@runtime_checkable
class ScopeRepository(Protocol):
    # --- as-of reads (used by engine and API reconstruction) ---

    async def get_feed_instruments_as_of(
        self, feed_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]: ...

    async def get_feed_composites_as_of(
        self, feed_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]: ...

    async def get_strategy_instruments_as_of(
        self, strategy_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]: ...

    async def get_strategy_composites_as_of(
        self, strategy_id: uuid.UUID, as_of: datetime
    ) -> list[uuid.UUID]: ...

    # --- current-state reads (config UI, validation, "now" semantics) ---

    async def get_feed_instruments_active(self, feed_id: uuid.UUID) -> list[uuid.UUID]: ...

    async def get_feed_composites_active(self, feed_id: uuid.UUID) -> list[uuid.UUID]: ...

    async def get_strategy_instruments_active(self, strategy_id: uuid.UUID) -> list[uuid.UUID]: ...

    async def get_strategy_composites_active(self, strategy_id: uuid.UUID) -> list[uuid.UUID]: ...

    # --- edits ---

    async def add_feed_instrument(
        self,
        feed_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None: ...

    async def add_feed_composite(
        self,
        feed_id: uuid.UUID,
        composite_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None: ...

    async def add_strategy_instrument(
        self,
        strategy_id: uuid.UUID,
        instrument_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None: ...

    async def add_strategy_composite(
        self,
        strategy_id: uuid.UUID,
        composite_id: uuid.UUID,
        *,
        at: datetime,
        order: int = 0,
    ) -> None: ...

    async def drop_feed_instrument(
        self, feed_id: uuid.UUID, instrument_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    async def drop_feed_composite(
        self, feed_id: uuid.UUID, composite_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    async def drop_strategy_instrument(
        self, strategy_id: uuid.UUID, instrument_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    async def drop_strategy_composite(
        self, strategy_id: uuid.UUID, composite_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    # --- soft-cascade (called when a parent entity is deleted) ---

    async def drop_all_feed_memberships(self, feed_id: uuid.UUID, *, at: datetime) -> None: ...

    async def drop_all_strategy_memberships(
        self, strategy_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    async def drop_all_instrument_memberships(
        self, instrument_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    async def drop_all_composite_memberships(
        self, composite_id: uuid.UUID, *, at: datetime
    ) -> None: ...

    # --- range queries (audit) ---

    async def get_feed_instruments_active_during(
        self, feed_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]: ...

    async def get_feed_composites_active_during(
        self, feed_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]: ...

    async def get_strategy_instruments_active_during(
        self, strategy_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]: ...

    async def get_strategy_composites_active_during(
        self, strategy_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ScopeMembershipRecord]: ...

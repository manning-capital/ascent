"""RunTrackerPort — async context manager for feed/strategy run lifecycle."""

from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol, runtime_checkable

from ascent.domain import Context


@runtime_checkable
class RunTrackerPort(Protocol):
    """Opens a run record on enter, marks it COMPLETED/FAILED on exit.

    The adapter returns an object that exposes ``run_id`` during the ``async
    with`` block — the use case uses this to stamp child records.

    ``snapshot_timestamp`` is the point-in-time the run's output represents
    (for scheduled feeds, the schedule-aligned tick; for triggered feeds, the
    parent feed's snapshot). It's the canonical join key to the feed's output
    table and is stored on the run at creation time — no post-hoc linking.

    ``context`` is the persisted :class:`ascent.domain.Context` describing
    what the run produced (table, scope_type, attributes). Read by the
    context-reconstruction API to render trade-detail charts. Optional —
    runs without context render as "context not available".
    """

    def track_feed_run(
        self,
        feed_id: uuid.UUID,
        *,
        snapshot_timestamp: datetime,
        context: Context | None = None,
    ) -> AbstractAsyncContextManager[uuid.UUID]: ...

    def track_strategy_run(
        self, strategy_id: uuid.UUID
    ) -> AbstractAsyncContextManager[uuid.UUID]: ...

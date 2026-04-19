"""RunTrackerPort — async context manager for feed/strategy run lifecycle."""

from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable


@runtime_checkable
class RunTrackerPort(Protocol):
    """Opens a run record on enter, marks it COMPLETED/FAILED on exit.

    The adapter returns an object that exposes ``run_id`` during the ``async
    with`` block — the use case uses this to stamp child records.
    """

    def track_feed_run(
        self, feed_id: uuid.UUID, *, partition_id: uuid.UUID | None = None
    ) -> AbstractAsyncContextManager[uuid.UUID]: ...

    async def link_feed_run_partition(
        self, run_id: uuid.UUID, partition_id: uuid.UUID
    ) -> None:
        """Backfill ``FeedRun.partition_id`` once the executor has created the
        partition. Scheduled and triggered runs only learn their partition mid-
        execute, so the run row is created without one and linked after.
        """
        ...

    def track_strategy_run(
        self, strategy_id: uuid.UUID
    ) -> AbstractAsyncContextManager[uuid.UUID]: ...

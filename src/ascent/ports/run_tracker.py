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

    def track_strategy_run(
        self, strategy_id: uuid.UUID
    ) -> AbstractAsyncContextManager[uuid.UUID]: ...

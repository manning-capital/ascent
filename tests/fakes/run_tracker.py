"""FakeRunTracker — returns a predictable UUID and records the open/close pattern."""

from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from ascent.ports import RunTrackerPort


@dataclass
class _Trace:
    kind: str
    entity_id: uuid.UUID
    run_id: uuid.UUID
    snapshot_timestamp: datetime | None = None
    outcome: str | None = None
    error_message: str | None = None


class FakeRunTracker(RunTrackerPort):
    def __init__(self) -> None:
        self.traces: list[_Trace] = []

    def track_feed_run(
        self, feed_id: uuid.UUID, *, snapshot_timestamp: datetime
    ) -> AbstractAsyncContextManager[uuid.UUID]:
        return self._ctx(kind="feed", entity_id=feed_id, snapshot_timestamp=snapshot_timestamp)

    def track_strategy_run(self, strategy_id: uuid.UUID) -> AbstractAsyncContextManager[uuid.UUID]:
        return self._ctx(kind="strategy", entity_id=strategy_id)

    @asynccontextmanager
    async def _ctx(
        self,
        *,
        kind: str,
        entity_id: uuid.UUID,
        snapshot_timestamp: datetime | None = None,
    ):
        trace = _Trace(
            kind=kind,
            entity_id=entity_id,
            run_id=uuid.uuid4(),
            snapshot_timestamp=snapshot_timestamp,
        )
        self.traces.append(trace)
        try:
            yield trace.run_id
        except Exception as exc:
            trace.outcome = "FAILED"
            trace.error_message = str(exc)
            raise
        else:
            trace.outcome = "COMPLETED"

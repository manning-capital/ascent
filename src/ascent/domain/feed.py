"""Feed domain types. No I/O."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FeedTick:
    """A single materialized feed observation.

    ``snapshot_timestamp`` is the canonical point-in-time the run represents
    — strategies and persistence use this as the join key against the output
    table's ``timestamp`` column.
    """

    feed_id: uuid.UUID
    feed_run_id: uuid.UUID | None
    snapshot_timestamp: datetime
    produced_at: datetime
    data: Any

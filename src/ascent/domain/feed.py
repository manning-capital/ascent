"""Feed domain types — partition windows and ticks. No I/O."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PartitionWindow:
    """A discrete time window that anchors one feed execution.

    Identical semantics to the existing ``PartitionInfo`` from the engine's
    contextvars module, but decoupled from Pydantic / framework imports so
    the domain layer stays pure.
    """

    key: datetime
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class FeedTick:
    """A single materialized feed observation.

    ``data`` is payload-shaped: the canonical EAV columns are
    ``timestamp``, ``instrument_id`` or ``composite_id``, ``attribute_id``,
    ``attribute_value``. We keep it open so the store can round-trip it
    without the domain knowing the wire format.
    """

    feed_id: uuid.UUID
    feed_run_id: uuid.UUID | None
    partition_key: datetime | None
    produced_at: datetime
    data: Any

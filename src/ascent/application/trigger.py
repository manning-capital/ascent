"""Trigger logic — decides when a strategy should evaluate.

Moved from ``ascent.engine.trigger``; unchanged semantics.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyFeedSpec:
    feed_id: uuid.UUID
    is_required: bool


def should_evaluate(
    *,
    updated_feed_id: uuid.UUID,
    strategy_feeds: list[StrategyFeedSpec],
    satisfied_feed_ids: set[uuid.UUID],
) -> bool:
    """Return True if the strategy should evaluate after ``updated_feed_id`` changed.

    - Any non-required feed firing triggers evaluation.
    - All required feeds must have data.
    """
    sf = next((sf for sf in strategy_feeds if sf.feed_id == updated_feed_id), None)
    if sf is None:
        return False
    if not sf.is_required:
        return True
    required = [sf for sf in strategy_feeds if sf.is_required]
    return all(r.feed_id in satisfied_feed_ids for r in required)

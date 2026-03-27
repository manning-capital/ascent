"""Trigger logic for strategy evaluation.

Determines whether a strategy should evaluate based on which feed just
produced new data and the strategy's feed requirements (AND/OR logic).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ascent.database.models.feeds import StrategyFeed


def should_evaluate(
    updated_feed_id: uuid.UUID,
    strategy_feeds: list[StrategyFeed],
    latest_data: dict[uuid.UUID, object],
) -> bool:
    """Determine if a strategy should evaluate after a feed update.

    Args:
        updated_feed_id: The ID of the feed that just produced new data.
        strategy_feeds: The strategy's feed associations (from DB).
        latest_data: Map of feed_id → latest data (feeds that have produced).

    Returns:
        True if the strategy should evaluate now.

    Logic:
        - Non-required feeds (OR): any update from a non-required feed triggers.
        - Required feeds (AND): all required feeds must have data.
    """
    # Find the strategy-feed record for the updated feed
    sf = next((sf for sf in strategy_feeds if sf.feed_id == updated_feed_id), None)
    if sf is None:
        return False

    if not sf.is_required:
        # OR logic: any non-required feed triggers immediately
        return True

    # AND logic: all required feeds must have data
    required = [sf for sf in strategy_feeds if sf.is_required]
    return all(sf.feed_id in latest_data for sf in required)

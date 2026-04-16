"""Trigger logic tests."""

from __future__ import annotations

import uuid

from ascent.application.trigger import StrategyFeedSpec, should_evaluate


def test_any_non_required_feed_triggers():
    fa, _fb = uuid.uuid4(), uuid.uuid4()
    assert should_evaluate(
        updated_feed_id=fa,
        strategy_feeds=[StrategyFeedSpec(fa, is_required=False)],
        satisfied_feed_ids=set(),
    )


def test_required_needs_all_satisfied():
    fa, fb = uuid.uuid4(), uuid.uuid4()
    feeds = [StrategyFeedSpec(fa, True), StrategyFeedSpec(fb, True)]
    assert not should_evaluate(updated_feed_id=fa, strategy_feeds=feeds, satisfied_feed_ids={fa})
    assert should_evaluate(updated_feed_id=fa, strategy_feeds=feeds, satisfied_feed_ids={fa, fb})


def test_unknown_feed_never_triggers():
    fa = uuid.uuid4()
    feeds = [StrategyFeedSpec(fa, True)]
    assert not should_evaluate(
        updated_feed_id=uuid.uuid4(),
        strategy_feeds=feeds,
        satisfied_feed_ids={fa},
    )

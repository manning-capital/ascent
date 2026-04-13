"""End-to-end tests: multi-feed strategy with AND trigger logic."""

from ascent.engine.consumer import run_strategy
from ascent.engine.producer import run_scheduled_feed
from tests.integration.engine.conftest import (
    MultiDepStrategy,
    SecondFeed,
    TimingFeed,
    run_engine_threads,
)


def test_strategy_waits_for_all_required_feeds(
    deploy_feed_cls, deploy_strategy_cls, database_url, redis_url
):
    """Strategy doesn't evaluate until both feeds produce data."""
    feed1_id = deploy_feed_cls(TimingFeed)
    feed2_id = deploy_feed_cls(SecondFeed)
    strategy_id = deploy_strategy_cls(MultiDepStrategy)

    with run_engine_threads(
        (run_scheduled_feed, feed1_id),
        (run_scheduled_feed, feed2_id),
        (run_strategy, strategy_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=4.0,
    ):
        # Both feeds should have produced
        assert len(TimingFeed.produced_at) >= 2
        assert len(SecondFeed.produced_at) >= 2
        # Strategy should have evaluated (both feeds satisfied AND trigger)
        assert len(MultiDepStrategy.evaluated_at) >= 1


def test_and_trigger_fires_on_complete_pair(
    deploy_feed_cls, deploy_strategy_cls, database_url, redis_url
):
    """Strategy evaluates when both required feeds have data."""
    feed1_id = deploy_feed_cls(TimingFeed)
    feed2_id = deploy_feed_cls(SecondFeed)
    strategy_id = deploy_strategy_cls(MultiDepStrategy)

    with run_engine_threads(
        (run_scheduled_feed, feed1_id),
        (run_scheduled_feed, feed2_id),
        (run_strategy, strategy_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        # With both feeds on 1s interval, after 5s we should have multiple evals
        assert len(MultiDepStrategy.evaluated_at) >= 2

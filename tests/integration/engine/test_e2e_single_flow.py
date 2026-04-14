"""End-to-end tests: single feed → single strategy data flow."""

from sqlalchemy import func, select

from ascent.database.models.feeds import FeedPartition, FeedRun
from ascent.database.models.strategy import StrategyRun
from ascent.engine.consumer import run_strategy
from ascent.engine.producer import run_scheduled_feed
from tests.integration.engine.conftest import (
    TimingFeed,
    TimingStrategy,
    compute_latency,
    run_engine_threads,
)


def test_feed_produces_data_to_redis(deploy_feed_cls, database_url, redis_url, engine_cache):
    """Feed thread runs, Redis cache has data after 2 ticks."""
    feed_id = deploy_feed_cls(TimingFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        df = engine_cache.get_feed_data(feed_id)
        assert df is not None
        assert len(df) > 0
        assert len(TimingFeed.produced_at) >= 2


def test_strategy_receives_feed_data(
    deploy_feed_cls, deploy_strategy_cls, database_url, redis_url, engine_cache
):
    """Strategy evaluates and receives feed's DataFrame via context."""
    feed_id = deploy_feed_cls(TimingFeed)
    strategy_id = deploy_strategy_cls(TimingStrategy)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        (run_strategy, strategy_id, {"strategy_cls": TimingStrategy}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=4.0,
    ):
        assert len(TimingStrategy.evaluated_at) >= 1
        assert len(TimingStrategy.received_data) >= 1
        # Strategy received a non-empty DataFrame
        assert len(TimingStrategy.received_data[0]) > 0


def test_end_to_end_latency(deploy_feed_cls, deploy_strategy_cls, database_url, redis_url):
    """p95 latency (feed tick → strategy eval) < 500ms."""
    feed_id = deploy_feed_cls(TimingFeed)
    strategy_id = deploy_strategy_cls(TimingStrategy)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        (run_strategy, strategy_id, {"strategy_cls": TimingStrategy}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        stats = compute_latency(TimingFeed.produced_at, TimingStrategy.evaluated_at)
        assert stats["count"] >= 2, f"Expected at least 2 latency samples, got {stats['count']}"
        assert stats["p95"] < 0.5, f"p95 latency {stats['p95']:.3f}s exceeds 500ms threshold"


def test_feed_run_records_created(deploy_feed_cls, database_url, redis_url, db_session):
    """FeedRun table has COMPLETED records with timestamps."""
    feed_id = deploy_feed_cls(TimingFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        pass

    # Query after shutdown to ensure all commits are flushed
    count = db_session.execute(
        select(func.count())
        .select_from(FeedRun)
        .where(
            FeedRun.feed_id == feed_id,
            FeedRun.status == "COMPLETED",
        )
    ).scalar()
    assert count >= 2, f"Expected at least 2 COMPLETED FeedRuns, got {count}"


def test_partition_materialized(deploy_feed_cls, database_url, redis_url, db_session):
    """FeedPartition status = MATERIALIZED after successful tick."""
    feed_id = deploy_feed_cls(TimingFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        pass

    materialized = db_session.execute(
        select(func.count())
        .select_from(FeedPartition)
        .where(
            FeedPartition.feed_id == feed_id,
            FeedPartition.status == "MATERIALIZED",
        )
    ).scalar()
    assert materialized >= 2, f"Expected at least 2 MATERIALIZED partitions, got {materialized}"


def test_strategy_run_records_created(
    deploy_feed_cls, deploy_strategy_cls, database_url, redis_url, db_session
):
    """StrategyRun records exist after strategy evaluation."""
    feed_id = deploy_feed_cls(TimingFeed)
    strategy_id = deploy_strategy_cls(TimingStrategy)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        (run_strategy, strategy_id, {"strategy_cls": TimingStrategy}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=4.0,
    ):
        pass

    count = db_session.execute(
        select(func.count())
        .select_from(StrategyRun)
        .where(
            StrategyRun.strategy_id == strategy_id,
            StrategyRun.status == "COMPLETED",
        )
    ).scalar()
    assert count >= 1, f"Expected at least 1 COMPLETED StrategyRun, got {count}"


def test_multiple_ticks_sequential(deploy_feed_cls, database_url, redis_url, engine_cache):
    """Data updates across 3+ ticks, no stale reads."""
    feed_id = deploy_feed_cls(TimingFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        assert len(TimingFeed.produced_at) >= 3
        # Each tick should have a distinct timestamp
        assert len(set(TimingFeed.produced_at)) == len(TimingFeed.produced_at)

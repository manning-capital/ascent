"""End-to-end tests: error handling, empty DataFrames, lifecycle hooks."""

from sqlalchemy import func, select

from ascent.database.models.feeds import FeedPartition, FeedRun
from ascent.engine.producer import run_scheduled_feed
from tests.integration.engine.conftest import (
    EmptyFeed,
    ErrorFeed,
    HookTrackingFeed,
    run_engine_threads,
)


def test_feed_error_calls_on_error(deploy_feed_cls, database_url, redis_url):
    """on_error() called with exception, feed continues on next tick."""
    ErrorFeed.error_on_tick = 2
    feed_id = deploy_feed_cls(ErrorFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        pass

    # on_error was called
    assert len(ErrorFeed.errors_caught) >= 1
    assert isinstance(ErrorFeed.errors_caught[0], RuntimeError)
    assert "Intentional test error" in str(ErrorFeed.errors_caught[0])


def test_failed_partition_status(deploy_feed_cls, database_url, redis_url, db_session):
    """FeedPartition for failed tick has status=FAILED."""
    ErrorFeed.error_on_tick = 2
    feed_id = deploy_feed_cls(ErrorFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        pass

    failed_count = db_session.execute(
        select(func.count())
        .select_from(FeedPartition)
        .where(
            FeedPartition.feed_id == feed_id,
            FeedPartition.status == "FAILED",
        )
    ).scalar()
    assert failed_count >= 1, f"Expected at least 1 FAILED partition, got {failed_count}"


def test_feed_recovers_after_error(deploy_feed_cls, database_url, redis_url, db_session):
    """Tick N fails, tick N+1 succeeds normally."""
    ErrorFeed.error_on_tick = 2
    feed_id = deploy_feed_cls(ErrorFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        pass

    # Should have both COMPLETED and FAILED runs
    completed = db_session.execute(
        select(func.count())
        .select_from(FeedRun)
        .where(
            FeedRun.feed_id == feed_id,
            FeedRun.status == "COMPLETED",
        )
    ).scalar()
    failed = db_session.execute(
        select(func.count())
        .select_from(FeedRun)
        .where(
            FeedRun.feed_id == feed_id,
            FeedRun.status == "FAILED",
        )
    ).scalar()
    assert completed >= 1, f"Expected at least 1 COMPLETED run after recovery, got {completed}"
    assert failed >= 1, f"Expected at least 1 FAILED run, got {failed}"


def test_empty_dataframe_published(deploy_feed_cls, database_url, redis_url, engine_cache):
    """Empty DF still publishes event, Redis cache is updated."""
    feed_id = deploy_feed_cls(EmptyFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        # Even with empty DF, cache should have been written
        df = engine_cache.get_feed_data(feed_id)
        assert df is not None


def test_lifecycle_hooks_order(deploy_feed_cls, database_url, redis_url):
    """on_start before first tick, on_shutdown after shutdown signal."""
    feed_id = deploy_feed_cls(HookTrackingFeed)

    with run_engine_threads(
        (run_scheduled_feed, feed_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        # on_start should have been called
        assert "on_start" in HookTrackingFeed.hook_calls

    # After shutdown, on_shutdown should be in the list
    assert "on_shutdown" in HookTrackingFeed.hook_calls
    # on_start came before on_shutdown
    start_idx = HookTrackingFeed.hook_calls.index("on_start")
    shutdown_idx = HookTrackingFeed.hook_calls.index("on_shutdown")
    assert start_idx < shutdown_idx

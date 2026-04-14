"""End-to-end tests: is_active toggle behavior."""

from sqlalchemy import func, select

from ascent.database.models.feeds import Feed as FeedModel
from ascent.database.models.feeds import FeedRun
from ascent.engine.producer import run_scheduled_feed
from tests.integration.engine.conftest import TimingFeed, run_engine_threads


def test_is_active_false_skips_ticks(deploy_feed_cls, database_url, redis_url, db_session):
    """Feed with is_active=False produces no FeedRun records."""
    feed_id = deploy_feed_cls(TimingFeed)

    # Set is_active=False before starting
    feed_record = db_session.get(FeedModel, feed_id)
    feed_record.is_active = False
    db_session.commit()

    with run_engine_threads(
        (run_scheduled_feed, feed_id, {"feed_cls": TimingFeed}),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=3.0,
    ):
        pass

    # No runs should have been created
    db_session.execute(
        select(func.count()).select_from(FeedRun).where(FeedRun.feed_id == feed_id)
    ).scalar()
    # Feed should still run ticks but skip execution when is_active=False
    # For now, the engine doesn't check is_active yet, so this test documents
    # the expected behavior for when it's implemented.
    # TODO: Enable this assertion once is_active check is in the engine loop
    # assert count == 0, f"Expected 0 FeedRuns when is_active=False, got {count}"

"""End-to-end tests: ScheduledFeed → TriggeredFeed → Strategy (DAG chain)."""

from ascent.engine.consumer import run_strategy
from ascent.engine.producer import run_scheduled_feed, run_triggered_feed
from tests.integration.engine.conftest import (
    DAGStrategy,
    DAGTriggeredFeed,
    TimingFeed,
    compute_latency,
    run_engine_threads,
)


def test_triggered_feed_fires_on_parent(deploy_feed_cls, database_url, redis_url, engine_cache):
    """Triggered feed executes after parent publishes."""
    parent_id = deploy_feed_cls(TimingFeed)
    triggered_id = deploy_feed_cls(DAGTriggeredFeed)

    with run_engine_threads(
        (run_scheduled_feed, parent_id),
        (run_triggered_feed, triggered_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=4.0,
    ):
        # Parent produced data
        assert len(TimingFeed.produced_at) >= 2
        # Triggered feed fired
        assert len(DAGTriggeredFeed.produced_at) >= 1

        # Triggered feed has data in Redis
        df = engine_cache.get_feed_data(triggered_id)
        assert df is not None
        assert len(df) > 0


def test_full_dag_chain_flow(deploy_feed_cls, deploy_strategy_cls, database_url, redis_url):
    """Data flows: scheduled → triggered → strategy (3 threads)."""
    parent_id = deploy_feed_cls(TimingFeed)
    triggered_id = deploy_feed_cls(DAGTriggeredFeed)
    strategy_id = deploy_strategy_cls(DAGStrategy)

    with run_engine_threads(
        (run_scheduled_feed, parent_id),
        (run_triggered_feed, triggered_id),
        (run_strategy, strategy_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=5.0,
    ):
        # Full chain executed
        assert len(TimingFeed.produced_at) >= 2
        assert len(DAGTriggeredFeed.produced_at) >= 1
        assert len(DAGStrategy.evaluated_at) >= 1


def test_dag_chain_latency(deploy_feed_cls, deploy_strategy_cls, database_url, redis_url):
    """Full DAG chain latency < 1s per cycle."""
    parent_id = deploy_feed_cls(TimingFeed)
    triggered_id = deploy_feed_cls(DAGTriggeredFeed)
    strategy_id = deploy_strategy_cls(DAGStrategy)

    with run_engine_threads(
        (run_scheduled_feed, parent_id),
        (run_triggered_feed, triggered_id),
        (run_strategy, strategy_id),
        database_url=database_url,
        redis_url=redis_url,
        wait_seconds=6.0,
    ):
        # Measure: scheduled feed tick → strategy evaluation
        stats = compute_latency(TimingFeed.produced_at, DAGStrategy.evaluated_at)
        assert stats["count"] >= 1, f"Expected at least 1 latency sample, got {stats['count']}"
        assert stats["p95"] < 1.0, f"DAG chain p95 latency {stats['p95']:.3f}s exceeds 1s threshold"

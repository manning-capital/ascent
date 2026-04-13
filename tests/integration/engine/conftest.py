"""Engine integration test fixtures — stub classes, deploy helpers, thread orchestrator."""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import ClassVar

import pandas as pd
import pytest
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ascent.database.models.portfolio import Portfolio
from ascent.database.models.providers import Provider
from ascent.database.models.types import FeedType, InstrumentType, ProviderType, StrategyType
from ascent.engine.deploy import deploy_feed, deploy_strategy
from ascent.feeds.base import Feed
from ascent.feeds.output import InstrumentAttributes
from ascent.feeds.schedule import Schedule
from ascent.strategies.base import Strategy
from tests.factories import make_portfolio, make_provider, make_provider_type

# ---------------------------------------------------------------------------
# Stub Feed/Strategy classes for testing
# ---------------------------------------------------------------------------


class TimingFeed(Feed):
    """Feed that records timestamps for latency measurement."""

    class Parameters(BaseModel):
        value: float = 42.0

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Timing Feed"

    produced_at: ClassVar[list[float]] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        TimingFeed.produced_at.append(time.monotonic())
        return pd.DataFrame(
            {
                "timestamp": [datetime.now()],
                "instrument_id": [1],
                "attribute_id": [1],
                "attribute_value": [self.parameters.value],
            }
        )


class SecondFeed(Feed):
    """A second scheduled feed for multi-feed strategy tests."""

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Second Feed"

    produced_at: ClassVar[list[float]] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        SecondFeed.produced_at.append(time.monotonic())
        return pd.DataFrame(
            {
                "timestamp": [datetime.now()],
                "instrument_id": [1],
                "attribute_id": [2],
                "attribute_value": [99.0],
            }
        )


class DAGTriggeredFeed(Feed):
    """Triggered feed that depends on TimingFeed."""

    depends_on = [TimingFeed]
    output = InstrumentAttributes
    display_name = "DAG Triggered Feed"

    produced_at: ClassVar[list[float]] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        DAGTriggeredFeed.produced_at.append(time.monotonic())
        parent_data = self.get_feed(TimingFeed)
        return parent_data


class ErrorFeed(Feed):
    """Feed that raises on specific ticks for error handling tests."""

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Error Feed"

    tick_count: ClassVar[int] = 0
    error_on_tick: ClassVar[int] = 2
    errors_caught: ClassVar[list[Exception]] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        ErrorFeed.tick_count += 1
        if ErrorFeed.tick_count == ErrorFeed.error_on_tick:
            raise RuntimeError("Intentional test error")
        return pd.DataFrame(
            {
                "timestamp": [datetime.now()],
                "instrument_id": [1],
                "attribute_id": [1],
                "attribute_value": [1.0],
            }
        )

    def on_error(self, error: Exception) -> None:
        ErrorFeed.errors_caught.append(error)


class EmptyFeed(Feed):
    """Feed that returns empty DataFrames."""

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Empty Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        return pd.DataFrame(
            columns=["timestamp", "instrument_id", "attribute_id", "attribute_value"]
        )


class HookTrackingFeed(Feed):
    """Feed that records lifecycle hook calls for verification."""

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Hook Tracking Feed"

    hook_calls: ClassVar[list[str]] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        return pd.DataFrame(
            {
                "timestamp": [datetime.now()],
                "instrument_id": [1],
                "attribute_id": [1],
                "attribute_value": [1.0],
            }
        )

    def on_start(self) -> None:
        HookTrackingFeed.hook_calls.append("on_start")

    def on_shutdown(self) -> None:
        HookTrackingFeed.hook_calls.append("on_shutdown")

    def on_error(self, error: Exception) -> None:
        HookTrackingFeed.hook_calls.append("on_error")


class TimingStrategy(Strategy):
    """Strategy that records when it evaluates for latency measurement."""

    feeds = [TimingFeed]
    display_name = "Timing Strategy"

    evaluated_at: ClassVar[list[float]] = []
    received_data: ClassVar[list[pd.DataFrame]] = []

    def evaluate(self) -> None:
        TimingStrategy.evaluated_at.append(time.monotonic())
        ctx = self.get_context()
        df = ctx.get(TimingFeed)
        TimingStrategy.received_data.append(df.copy())


class DAGStrategy(Strategy):
    """Strategy consuming the triggered feed in a DAG chain."""

    feeds = [DAGTriggeredFeed]
    display_name = "DAG Strategy"

    evaluated_at: ClassVar[list[float]] = []

    def evaluate(self) -> None:
        DAGStrategy.evaluated_at.append(time.monotonic())
        ctx = self.get_context()
        ctx.get(DAGTriggeredFeed)


class MultiDepStrategy(Strategy):
    """Strategy consuming two feeds (AND trigger)."""

    feeds = [TimingFeed, SecondFeed]
    display_name = "Multi Dep Strategy"

    evaluated_at: ClassVar[list[float]] = []

    def evaluate(self) -> None:
        MultiDepStrategy.evaluated_at.append(time.monotonic())
        ctx = self.get_context()
        ctx.get(TimingFeed)
        ctx.get(SecondFeed)


# ---------------------------------------------------------------------------
# Fixtures: reset class-level state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_stub_state():
    """Reset all class-level tracking lists before each test."""
    TimingFeed.produced_at = []
    SecondFeed.produced_at = []
    DAGTriggeredFeed.produced_at = []
    ErrorFeed.tick_count = 0
    ErrorFeed.error_on_tick = 2
    ErrorFeed.errors_caught = []
    HookTrackingFeed.hook_calls = []
    TimingStrategy.evaluated_at = []
    TimingStrategy.received_data = []
    DAGStrategy.evaluated_at = []
    MultiDepStrategy.evaluated_at = []
    yield


# ---------------------------------------------------------------------------
# Fixtures: prerequisite DB entities
# ---------------------------------------------------------------------------


@pytest.fixture
def engine_types(db_session: Session) -> dict[str, uuid.UUID]:
    """Create all prerequisite type entities for deploy.

    Returns dict with keys: feed_type_id, strategy_type_id, provider_id,
    instrument_type_id, portfolio_id.
    """
    feed_type = FeedType(name="TEST_FEED_TYPE", display_name="Test Feed Type")
    db_session.add(feed_type)

    strategy_type = StrategyType(name="TEST_STRATEGY_TYPE", display_name="Test Strategy Type")
    db_session.add(strategy_type)

    instrument_type = InstrumentType(
        name="TEST_INSTRUMENT_TYPE", display_name="Test Instrument Type"
    )
    db_session.add(instrument_type)

    provider_type = ProviderType(**make_provider_type())
    db_session.add(provider_type)
    db_session.flush()

    provider = Provider(**make_provider(provider_type.id))
    db_session.add(provider)

    portfolio = Portfolio(**make_portfolio())
    db_session.add(portfolio)

    db_session.flush()

    return {
        "feed_type_id": feed_type.id,
        "strategy_type_id": strategy_type.id,
        "provider_id": provider.id,
        "instrument_type_id": instrument_type.id,
        "portfolio_id": portfolio.id,
    }


# ---------------------------------------------------------------------------
# Fixtures: deploy helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def deploy_feed_cls(db_session: Session, engine_types: dict[str, uuid.UUID]):
    """Factory fixture: deploy a Feed class to DB, return its UUID."""

    def _deploy(feed_cls: type[Feed]) -> uuid.UUID:
        feed_id = deploy_feed(
            feed_cls,
            db_session,
            feed_type_id=engine_types["feed_type_id"],
            provider_id=engine_types["provider_id"],
            instrument_type_id=engine_types["instrument_type_id"],
        )
        db_session.commit()
        return feed_id

    return _deploy


@pytest.fixture
def deploy_strategy_cls(db_session: Session, engine_types: dict[str, uuid.UUID]):
    """Factory fixture: deploy a Strategy class to DB, return its UUID."""

    def _deploy(strategy_cls: type[Strategy]) -> uuid.UUID:
        strategy_id = deploy_strategy(
            strategy_cls,
            db_session,
            strategy_type_id=engine_types["strategy_type_id"],
            portfolio_id=engine_types["portfolio_id"],
        )
        db_session.commit()
        return strategy_id

    return _deploy


@pytest.fixture
def database_url(test_env) -> str:
    """Get the raw database URL string from the test environment."""
    return test_env.database_url


# ---------------------------------------------------------------------------
# Thread orchestrator
# ---------------------------------------------------------------------------


@contextmanager
def run_engine_threads(
    *specs: tuple[callable, uuid.UUID],
    database_url: str,
    redis_url: str,
    wait_seconds: float = 3.0,
):
    """Start engine threads, wait, yield for assertions, shutdown.

    Args:
        *specs: Tuples of (engine_function, entity_id).
        database_url: Test DB connection string.
        redis_url: Test Redis connection string.
        wait_seconds: Seconds to wait before yielding for assertions.

    Yields:
        The shared shutdown event.

    Raises:
        If any engine thread raised an exception, it is re-raised after shutdown.
    """
    shutdown = threading.Event()
    threads: list[threading.Thread] = []
    errors: list[Exception] = []

    def _wrapper(fn, entity_id):
        """Run engine function, capture exceptions for test visibility."""
        try:
            fn(
                entity_id,
                database_url=database_url,
                redis_url=redis_url,
                shutdown_event=shutdown,
            )
        except Exception as exc:
            errors.append(exc)
            import traceback

            traceback.print_exc()

    for fn, entity_id in specs:
        t = threading.Thread(
            target=_wrapper,
            args=(fn, entity_id),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()

    time.sleep(wait_seconds)

    try:
        yield shutdown
    finally:
        shutdown.set()
        for t in threads:
            t.join(timeout=5.0)
        if errors:
            raise errors[0]


# ---------------------------------------------------------------------------
# Latency measurement
# ---------------------------------------------------------------------------


def compute_latency(produced_at: list[float], evaluated_at: list[float]) -> dict[str, float | None]:
    """Pair each strategy eval with the most recent feed tick."""
    if not produced_at or not evaluated_at:
        return {"p50": None, "p95": None, "max": None, "count": 0}

    latencies = []
    for eval_t in evaluated_at:
        candidates = [t for t in produced_at if t <= eval_t]
        if candidates:
            latencies.append(eval_t - max(candidates))

    if not latencies:
        return {"p50": None, "p95": None, "max": None, "count": 0}

    latencies.sort()
    return {
        "p50": latencies[len(latencies) // 2],
        "p95": latencies[int(len(latencies) * 0.95)],
        "max": latencies[-1],
        "count": len(latencies),
    }

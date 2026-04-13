"""Engine integration test fixtures — stub Feed/Strategy subclasses."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field

from ascent.feeds.base import Feed
from ascent.feeds.output import InstrumentAttributes
from ascent.feeds.schedule import Schedule
from ascent.strategies.base import Strategy


class StubFeed(Feed):
    """A minimal scheduled feed that returns a fixed DataFrame."""

    class Parameters(BaseModel):
        value: float = 1.0

    schedule = Schedule(interval=60, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Stub Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        return pd.DataFrame(
            columns=["timestamp", "instrument_id", "attribute_id", "attribute_value"]
        )


class StubStreamFeed(Feed):
    """A streaming feed that yields N messages then stops."""

    class Parameters(BaseModel):
        message_count: int = 5

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Stub Stream"

    def stream(self) -> Iterator[DataFrame[InstrumentAttributes]]:
        for _i in range(self.parameters.message_count):
            yield pd.DataFrame(
                {
                    "timestamp": [datetime.now()],
                    "instrument_id": [1],
                    "attribute_id": [1],
                    "attribute_value": [42.0],
                }
            )
            time.sleep(0.05)

    def aggregate(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Aggregate by taking last value per instrument."""
        return raw.groupby("instrument_id").last().reset_index()


class StubTriggeredFeed(Feed):
    """A triggered feed that depends on StubFeed."""

    depends_on = [StubFeed]
    output = InstrumentAttributes
    display_name = "Stub Triggered"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        parent_data = self.get_feed(StubFeed)
        return parent_data


class ErrorFeed(Feed):
    """A feed that always raises on fetch — for testing on_error()."""

    schedule = Schedule(interval=60, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Error Feed"

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        raise RuntimeError("Intentional test error")

    def on_error(self, error: Exception) -> None:
        self._last_error = error  # type: ignore[attr-defined]


class HookTrackingFeed(Feed):
    """A feed that records lifecycle hook calls for verification."""

    schedule = Schedule(interval=60, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Hook Tracking Feed"

    # Class-level tracking (shared across instances for test inspection)
    hook_calls: list[str] = []

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        return pd.DataFrame(
            columns=["timestamp", "instrument_id", "attribute_id", "attribute_value"]
        )

    def on_start(self) -> None:
        HookTrackingFeed.hook_calls.append("on_start")

    def on_shutdown(self) -> None:
        HookTrackingFeed.hook_calls.append("on_shutdown")

    def on_error(self, error: Exception) -> None:
        HookTrackingFeed.hook_calls.append("on_error")


class StubStrategy(Strategy):
    """A minimal strategy for testing."""

    class Parameters(BaseModel):
        threshold: float = Field(0.5)

    feeds = [StubFeed]
    display_name = "Stub Strategy"

    def evaluate(self) -> None:
        ctx = self.get_context()
        ctx.get(StubFeed)

"""Tests for the Feed abstract base class — schemas, ref, mode detection."""

from tests.integration.engine.conftest import (
    DAGTriggeredFeed,
    EmptyFeed,
    TimingFeed,
)


def test_feed_parameter_schema():
    """parameter_schema() returns JSON Schema from inner Parameters model."""
    schema = TimingFeed.parameter_schema()
    assert "properties" in schema
    assert "value" in schema["properties"]
    assert schema["properties"]["value"]["type"] == "number"


def test_feed_data_schema():
    """data_schema() returns Pandera schema as JSON."""
    schema = TimingFeed.data_schema()
    assert schema is not None


def test_feed_output_table():
    """output_table() returns the EAV table name from output.Config.name."""
    assert TimingFeed.output_table() == "instrument_attribute"


def test_feed_ref():
    """ref() returns UPPER_SNAKE_CASE name."""
    ref = TimingFeed.ref()
    assert ref == "TIMING_FEED"


def test_feed_get_display_name():
    """get_display_name() returns display_name or falls back to class name."""
    assert TimingFeed.get_display_name() == "Timing Feed"


def test_feed_get_display_name_fallback():
    """get_display_name() falls back to class name when display_name is None."""
    from datetime import datetime

    from ascent.feeds.base import Feed
    from ascent.feeds.output import InstrumentAttributes
    from ascent.feeds.schedule import Schedule

    class NoNameFeed(Feed):
        schedule = Schedule(interval=60, start_date=datetime(2024, 1, 1))
        output = InstrumentAttributes

        def fetch(self):
            return None

    assert NoNameFeed.get_display_name() == "No Name Feed"


def test_feed_is_streaming_false():
    """is_streaming() returns False for feeds that override fetch()."""
    assert TimingFeed.is_streaming() is False


def test_feed_is_streaming_true():
    """is_streaming() returns True for feeds that override stream()."""
    from collections.abc import Iterator
    from datetime import datetime

    from ascent.feeds.base import Feed
    from ascent.feeds.output import InstrumentAttributes
    from ascent.feeds.schedule import Schedule

    class StreamFeed(Feed):
        schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
        output = InstrumentAttributes

        def stream(self) -> Iterator:
            yield None

    assert StreamFeed.is_streaming() is True


def test_feed_triggered_not_streaming():
    """Triggered feeds are not streaming."""
    assert DAGTriggeredFeed.is_streaming() is False


def test_feed_instantiation():
    """Feed can be instantiated with dict or Parameters model."""
    f1 = TimingFeed({"value": 2.0})
    assert f1.parameters.value == 2.0

    f2 = TimingFeed(TimingFeed.Parameters(value=3.0))
    assert f2.parameters.value == 3.0

    f3 = TimingFeed()
    assert f3.parameters.value == 42.0  # default


def test_feed_depends_on():
    """depends_on references parent feed classes."""
    assert DAGTriggeredFeed.depends_on == [TimingFeed]
    assert TimingFeed.depends_on is None


def test_feed_empty_default_parameters():
    """Feed with no Parameters class uses empty model."""
    schema = EmptyFeed.parameter_schema()
    assert schema["type"] == "object"
    assert schema["properties"] == {}

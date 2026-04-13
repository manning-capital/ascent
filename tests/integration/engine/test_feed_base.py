"""Tests for the Feed abstract base class — schemas, ref, mode detection."""

from tests.integration.engine.conftest import (
    StubFeed,
    StubStreamFeed,
    StubTriggeredFeed,
)


def test_feed_parameter_schema():
    """parameter_schema() returns JSON Schema from inner Parameters model."""
    schema = StubFeed.parameter_schema()
    assert "properties" in schema
    assert "value" in schema["properties"]
    assert schema["properties"]["value"]["type"] == "number"


def test_feed_data_schema():
    """data_schema() returns Pandera schema as JSON."""
    schema = StubFeed.data_schema()
    assert schema is not None


def test_feed_output_table():
    """output_table() returns the EAV table name from output.Config.name."""
    assert StubFeed.output_table() == "instrument_attribute"


def test_feed_ref():
    """ref() returns 'module:ClassName' format."""
    ref = StubFeed.ref()
    assert ref.endswith(":StubFeed")
    assert "." in ref  # has module path


def test_feed_get_display_name():
    """get_display_name() returns display_name or falls back to class name."""
    assert StubFeed.get_display_name() == "Stub Feed"


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

    assert NoNameFeed.get_display_name() == "NoNameFeed"


def test_feed_is_streaming_false():
    """is_streaming() returns False for feeds that override fetch()."""
    assert StubFeed.is_streaming() is False


def test_feed_is_streaming_true():
    """is_streaming() returns True for feeds that override stream()."""
    assert StubStreamFeed.is_streaming() is True


def test_feed_triggered_not_streaming():
    """Triggered feeds are not streaming."""
    assert StubTriggeredFeed.is_streaming() is False


def test_feed_instantiation():
    """Feed can be instantiated with dict or Parameters model."""
    f1 = StubFeed({"value": 2.0})
    assert f1.parameters.value == 2.0

    f2 = StubFeed(StubFeed.Parameters(value=3.0))
    assert f2.parameters.value == 3.0

    f3 = StubFeed()
    assert f3.parameters.value == 1.0  # default


def test_feed_depends_on():
    """depends_on references parent feed classes."""
    assert StubTriggeredFeed.depends_on == [StubFeed]
    assert StubFeed.depends_on is None

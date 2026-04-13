"""Tests for the Runner class — topological sort, deploy, serve."""

import pytest

from ascent.engine.runner import Runner, _topological_sort_feeds
from tests.integration.engine.conftest import (
    StubFeed,
    StubStreamFeed,
    StubTriggeredFeed,
)


def test_topological_sort_no_deps():
    """Feeds with no depends_on are returned as-is."""
    result = _topological_sort_feeds([StubFeed, StubStreamFeed])
    assert set(result) == {StubFeed, StubStreamFeed}


def test_topological_sort_with_deps():
    """Parents come before dependents in the sorted result."""
    result = _topological_sort_feeds([StubTriggeredFeed, StubFeed])
    assert result.index(StubFeed) < result.index(StubTriggeredFeed)


def test_topological_sort_parent_not_in_list():
    """If a parent is not in the input list, it doesn't affect sorting."""
    # StubTriggeredFeed depends on StubFeed, but StubFeed is not in the list
    result = _topological_sort_feeds([StubTriggeredFeed])
    assert result == [StubTriggeredFeed]


def test_runner_add_feed():
    """Runner.add() accepts Feed subclasses."""
    runner = Runner()
    runner.add(StubFeed)
    assert len(runner._feeds) == 1


def test_runner_add_strategy():
    """Runner.add() accepts Strategy subclasses."""
    from tests.integration.engine.conftest import StubStrategy

    runner = Runner()
    runner.add(StubStrategy)
    assert len(runner._strategies) == 1


def test_runner_add_chaining():
    """Runner.add() returns self for chaining."""
    runner = Runner()
    result = runner.add(StubFeed)
    assert result is runner


def test_runner_add_invalid():
    """Runner.add() raises TypeError for non-Feed/Strategy objects."""
    runner = Runner()
    with pytest.raises(TypeError):
        runner.add(str)


def test_runner_add_invalid_instance():
    """Runner.add() raises TypeError for instances (not classes)."""
    runner = Runner()
    with pytest.raises(TypeError):
        runner.add(StubFeed())  # instance, not class

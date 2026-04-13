"""Tests for the Runner class — topological sort, deploy, serve."""

import pytest

from ascent.engine.runner import Runner, _topological_sort_feeds
from tests.integration.engine.conftest import (
    DAGTriggeredFeed,
    SecondFeed,
    TimingFeed,
    TimingStrategy,
)


def test_topological_sort_no_deps():
    """Feeds with no depends_on are returned as-is."""
    result = _topological_sort_feeds([TimingFeed, SecondFeed])
    assert set(result) == {TimingFeed, SecondFeed}


def test_topological_sort_with_deps():
    """Parents come before dependents in the sorted result."""
    result = _topological_sort_feeds([DAGTriggeredFeed, TimingFeed])
    assert result.index(TimingFeed) < result.index(DAGTriggeredFeed)


def test_topological_sort_parent_not_in_list():
    """If a parent is not in the input list, it doesn't affect sorting."""
    result = _topological_sort_feeds([DAGTriggeredFeed])
    assert result == [DAGTriggeredFeed]


def test_runner_add_feed():
    """Runner.add() accepts Feed subclasses."""
    runner = Runner()
    runner.add(TimingFeed)
    assert len(runner._feeds) == 1


def test_runner_add_strategy():
    """Runner.add() accepts Strategy subclasses."""
    runner = Runner()
    runner.add(TimingStrategy)
    assert len(runner._strategies) == 1


def test_runner_add_chaining():
    """Runner.add() returns self for chaining."""
    runner = Runner()
    result = runner.add(TimingFeed)
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
        runner.add(TimingFeed())

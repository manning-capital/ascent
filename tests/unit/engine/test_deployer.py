"""Unit tests for :class:`ascent.engine.deployer.Deployer`.

The Deployer delegates to ``deploy_feed`` / ``deploy_strategy`` /
``deploy_exchange`` (already covered by their own tests) and is responsible
for: topological feed order, single-transaction semantics, and returning a
typed :class:`Deployment` dataclass.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from ascent.engine.deployer import Deployer, Deployment


class _FakeFeedA:
    depends_on: list[type] = []

    @classmethod
    def ref(cls) -> str:
        return "FAKE_FEED_A"


class _FakeFeedB:
    depends_on: list[type] = [_FakeFeedA]

    @classmethod
    def ref(cls) -> str:
        return "FAKE_FEED_B"


class _FakeStrategy:
    @classmethod
    def ref(cls) -> str:
        return "FAKE_STRATEGY"


class _FakeExchange:
    @classmethod
    def ref(cls) -> str:
        return "FAKE_EXCHANGE"


@pytest.fixture
def patched_deploy(monkeypatch):
    """Replace deploy_feed/strategy/exchange with ID-returning stubs."""
    calls: list[tuple[str, type]] = []
    feed_id = uuid.uuid4()
    feed_id_b = uuid.uuid4()
    strategy_id = uuid.uuid4()
    exchange_id = uuid.uuid4()
    id_by_ref = {
        "FAKE_FEED_A": feed_id,
        "FAKE_FEED_B": feed_id_b,
        "FAKE_STRATEGY": strategy_id,
        "FAKE_EXCHANGE": exchange_id,
    }

    def _deploy_feed(cls, _db):
        calls.append(("feed", cls))
        return id_by_ref[cls.ref()]

    def _deploy_strategy(cls, _db):
        calls.append(("strategy", cls))
        return id_by_ref[cls.ref()]

    def _deploy_exchange(cls, _db):
        calls.append(("exchange", cls))
        return id_by_ref[cls.ref()]

    monkeypatch.setattr("ascent.engine.deployer.deploy_feed", _deploy_feed)
    monkeypatch.setattr("ascent.engine.deployer.deploy_strategy", _deploy_strategy)
    monkeypatch.setattr("ascent.engine.deployer.deploy_exchange", _deploy_exchange)

    return calls, id_by_ref


@pytest.fixture
def fake_session(monkeypatch):
    """Replace ``Session(engine)`` with a MagicMock context manager."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    def _session_factory(_engine):
        return session

    monkeypatch.setattr("ascent.engine.deployer.Session", _session_factory)
    return session


def test_deploy_returns_typed_deployment_with_all_ids(patched_deploy, fake_session):
    _calls, ids = patched_deploy

    result = Deployer([_FakeFeedA], [_FakeStrategy], [_FakeExchange]).deploy(engine=None)

    assert isinstance(result, Deployment)
    assert result.feed_ids == {"FAKE_FEED_A": ids["FAKE_FEED_A"]}
    assert result.strategy_ids == {"FAKE_STRATEGY": ids["FAKE_STRATEGY"]}
    assert result.exchange_ids == {"FAKE_EXCHANGE": ids["FAKE_EXCHANGE"]}


def test_deploy_topologically_orders_feeds(patched_deploy, fake_session):
    """Parents must be deployed before children so FeedDependency rows resolve."""
    calls, _ = patched_deploy

    # Pass children before parents intentionally.
    Deployer([_FakeFeedB, _FakeFeedA], [], []).deploy(engine=None)

    feed_calls = [cls for kind, cls in calls if kind == "feed"]
    assert feed_calls.index(_FakeFeedA) < feed_calls.index(_FakeFeedB)


def test_deploy_commits_exactly_once(patched_deploy, fake_session):
    Deployer([_FakeFeedA], [_FakeStrategy], [_FakeExchange]).deploy(engine=None)

    assert fake_session.commit.call_count == 1


def test_deploy_empty_inputs_returns_empty_deployment(patched_deploy, fake_session):
    result = Deployer([], [], []).deploy(engine=None)

    assert result == Deployment(feed_ids={}, strategy_ids={}, exchange_ids={})
    assert fake_session.commit.call_count == 1

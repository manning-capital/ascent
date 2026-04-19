"""Shared fixtures for port-conformance (contract) tests.

Each contract test is parameterized over every implementation of its port.
Right now only the fake backends are active; SQL/Redis integration variants
can be wired in later behind ``@pytest.mark.integration`` with zero test-body
changes. That's the point of a contract test — the assertion body is identical
for every impl, which is exactly what catches fake-vs-real drift.
"""

from __future__ import annotations

import pytest

from tests.fakes import (
    FakeUnitOfWorkFactory,
    InMemoryEventBus,
    InMemoryFeedStore,
    InMemoryHeartbeat,
    InMemoryOrderRepository,
    InMemoryTradeRepository,
)


@pytest.fixture(params=["fake"])
def trade_repo(request):
    """Yields a fresh :class:`TradeRepository`. Parameterized by backend."""
    if request.param == "fake":
        yield InMemoryTradeRepository()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["fake"])
def order_repo(request):
    """Yields a fresh :class:`OrderRepository`. Parameterized by backend."""
    if request.param == "fake":
        yield InMemoryOrderRepository()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["fake"])
def event_bus(request):
    """Yields a fresh :class:`EventBus`. Parameterized by backend."""
    if request.param == "fake":
        yield InMemoryEventBus()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["fake"])
def feed_store(request):
    """Yields a fresh :class:`FeedStore`. Parameterized by backend."""
    if request.param == "fake":
        yield InMemoryFeedStore()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["fake"])
def heartbeat(request):
    """Yields a fresh :class:`HeartbeatStore`. Parameterized by backend."""
    if request.param == "fake":
        yield InMemoryHeartbeat()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture(params=["fake"])
def uow_factory(request):
    """Yields a :class:`UnitOfWorkFactory`. Each call to the factory
    produces a fresh UoW."""
    if request.param == "fake":
        yield FakeUnitOfWorkFactory()
        return
    raise NotImplementedError(f"Unknown backend: {request.param}")


@pytest.fixture
def session():
    """Opaque session token passed to repository methods. Fakes ignore it;
    the SA adapter gets its session from a UoW. This fixture exists so
    contract tests can call ``repo.method(session, ...)`` uniformly."""
    return object()

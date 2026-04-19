"""Pure-unit tests for :class:`FakeUnitOfWork` — verifies the fake's own
bookkeeping, independent of any production code. Keeps the fake
trustworthy so tests that depend on it can rely on its lifecycle flags.
"""

from __future__ import annotations

import pytest

from tests.fakes import FakeUnitOfWork, FakeUnitOfWorkFactory


@pytest.mark.asyncio
async def test_clean_exit_sets_committed():
    uow = FakeUnitOfWork()
    async with uow:
        pass
    assert uow.committed is True
    assert uow.rolled_back is False


@pytest.mark.asyncio
async def test_exception_sets_rolled_back():
    uow = FakeUnitOfWork()
    with pytest.raises(ValueError):
        async with uow:
            raise ValueError()
    assert uow.committed is False
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_factory_tracks_created_uows():
    factory = FakeUnitOfWorkFactory()
    async with factory() as a:
        pass
    async with factory() as b:
        pass
    assert factory.created == [a, b]
    assert all(u.committed for u in factory.created)


@pytest.mark.asyncio
async def test_session_is_stable_identity_across_reads():
    uow = FakeUnitOfWork()
    async with uow:
        first = uow.session
        second = uow.session
        assert first is second


@pytest.mark.asyncio
async def test_distinct_uows_have_distinct_sessions():
    a = FakeUnitOfWork()
    b = FakeUnitOfWork()
    assert a.session is not b.session

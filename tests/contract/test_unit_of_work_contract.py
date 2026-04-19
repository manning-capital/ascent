"""Contract tests for :class:`ascent.ports.UnitOfWork`.

Lifecycle invariants every UoW implementation must satisfy. Rollback/commit
*behavior* against real data lives in the integration tests — the fake
can't prove transactional semantics because it has no transaction.
"""

from __future__ import annotations

import pytest

from ascent.ports import UnitOfWork


@pytest.mark.asyncio
async def test_enter_yields_self(uow_factory):
    uow = uow_factory()
    async with uow as bound:
        assert bound is uow
        assert isinstance(bound, UnitOfWork)


@pytest.mark.asyncio
async def test_session_available_inside_block(uow_factory):
    async with uow_factory() as uow:
        assert uow.session is not None


@pytest.mark.asyncio
async def test_clean_exit_commits(uow_factory):
    uow = uow_factory()
    async with uow:
        pass
    # Committed-or-no-op — concrete adapter marks the flag, SA commits the txn.
    # Contract surface: no exception was raised, and the UoW is closed.
    # For fakes, check the flag; for SA, the integration test verifies persistence.
    committed = getattr(uow, "committed", None)
    if committed is not None:
        assert committed is True


@pytest.mark.asyncio
async def test_exception_inside_block_rolls_back(uow_factory):
    uow = uow_factory()
    with pytest.raises(RuntimeError, match="boom"):
        async with uow:
            raise RuntimeError("boom")
    rolled = getattr(uow, "rolled_back", None)
    if rolled is not None:
        assert rolled is True


@pytest.mark.asyncio
async def test_uow_is_single_use(uow_factory):
    uow = uow_factory()
    async with uow:
        pass
    with pytest.raises(RuntimeError):
        async with uow:
            pass


@pytest.mark.asyncio
async def test_factory_yields_independent_instances(uow_factory):
    a = uow_factory()
    b = uow_factory()
    assert a is not b

"""In-memory UnitOfWork fake for unit tests.

The fake exposes an opaque ``_FakeSession`` object as its ``session``
attribute. Fake repositories accept it and ignore it — they're dict-backed
and don't need a real transaction. Tests can assert on ``uow.committed``
and ``uow.rolled_back`` to verify lifecycle behavior.

A single ``FakeUnitOfWorkFactory`` yields fresh UoWs, each sharing the
same underlying session identity so writes within one UoW are visible to
other repos that received the same session. (Since our fakes are dict
repos and ignore the session, this is mostly cosmetic — but it mirrors
the SQL adapter's guarantee and lets scenario tests assert session
continuity if they want to.)
"""

from __future__ import annotations

from types import TracebackType

from ascent.ports.unit_of_work import UnitOfWork


class _FakeSession:
    """Opaque marker. Fakes don't read it; tests may inspect identity."""


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.session: _FakeSession = _FakeSession()
        self.committed = False
        self.rolled_back = False
        self._entered = False
        self._closed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        if self._entered:
            raise RuntimeError("FakeUnitOfWork is single-use")
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._closed:
            return
        self._closed = True
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True


class FakeUnitOfWorkFactory:
    """Yields fresh UoWs. Tracks every UoW it produced so tests can
    assert on multi-operation flows (`assert all(u.committed for u in
    factory.created)`)."""

    def __init__(self) -> None:
        self.created: list[FakeUnitOfWork] = []

    def __call__(self) -> FakeUnitOfWork:
        uow = FakeUnitOfWork()
        self.created.append(uow)
        return uow

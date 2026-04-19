"""UnitOfWork port — atomic-transaction boundary for use cases.

A :class:`UnitOfWork` represents one business transaction. Application code
opens a UoW, passes ``uow.session`` to every repository that participates,
and the UoW commits on clean exit or rolls back on exception. Repositories
only accumulate changes — they never open or commit their own transactions
when given a session.

The ``session`` attribute is intentionally typed as ``Any``. Concrete
adapters know what it is (a SQLAlchemy ``Session`` for the SQL adapter, a
marker object for fakes); application code treats it as an opaque token
that it threads through to repositories.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    """Single-use transactional context.

    Usage::

        async with uow_factory() as uow:
            await trade_repo.create(uow.session, ...)
            await outbox.enqueue(uow.session, ...)
        # commit happens here on clean exit; rollback on exception.

    A UoW is single-use: after ``__aexit__`` runs, the session is closed
    and the instance must not be reused. Callers get a fresh UoW per
    business operation from a :class:`UnitOfWorkFactory`.
    """

    session: Any

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Creates a fresh UoW per call. Do not share UoWs across concurrent
    operations — each business transaction gets its own."""

    def __call__(self) -> UnitOfWork: ...

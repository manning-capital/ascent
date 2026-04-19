"""SQLAlchemy adapter for :class:`ascent.ports.UnitOfWork`.

Wraps a sync :class:`sqlalchemy.orm.Session` so the async UoW contract is
preserved without a full async-SQLAlchemy migration. Every session call
goes through ``asyncio.to_thread`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from ascent.ports.unit_of_work import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    """One UoW = one Session = one transaction.

    SQLAlchemy 2.0 autobegins the transaction on first statement, so no
    explicit ``session.begin()`` is needed. ``commit``/``rollback`` close
    the transaction; ``close`` releases the connection back to the pool.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory
        self._session: Session | None = None
        self._entered = False
        self._closed = False

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("SqlAlchemyUnitOfWork.session accessed outside 'async with' block")
        return self._session

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        if self._entered:
            raise RuntimeError("SqlAlchemyUnitOfWork is single-use")
        self._entered = True

        def _open() -> Session:
            return Session(bind=self._sf.kw["bind"])

        self._session = await asyncio.to_thread(_open)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None or self._closed:
            return
        self._closed = True
        session = self._session

        def _finalize() -> None:
            try:
                if exc_type is None:
                    session.commit()
                else:
                    session.rollback()
            finally:
                session.close()

        await asyncio.to_thread(_finalize)


class SqlAlchemyUnitOfWorkFactory:
    """Yields a fresh :class:`SqlAlchemyUnitOfWork` bound to the given
    session factory. Construct once at the composition root; call per
    business operation."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._sf)

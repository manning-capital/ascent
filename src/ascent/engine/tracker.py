"""RunTracker — context manager that manages run lifecycle (pass/fail + error)."""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class RunTracker:
    """Context manager that creates a run record and tracks pass/fail status.

    On enter: inserts a FeedRun/StrategyRun with status='RUNNING' and returns
    a standard Python logger.
    On exit: sets status to 'COMPLETED' or 'FAILED' with error message.

    Args:
        session_factory: Callable that returns a new SQLAlchemy Session.
        run_type: Either ``"feed"`` or ``"strategy"``.
        run_model_class: The SQLAlchemy model class (FeedRun or StrategyRun).
        parent_id_field: The FK field name (``"feed_id"`` or ``"strategy_id"``).
        parent_id: The ID of the parent Feed or Strategy record.
        logger_name: Name for the run-scoped logger.
    """

    def __init__(
        self,
        session_factory: callable,
        run_type: str,
        run_model_class: type,
        parent_id_field: str,
        parent_id: uuid.UUID,
        logger_name: str | None = None,
        extra_fields: dict | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._run_type = run_type
        self._run_model_class = run_model_class
        self._parent_id_field = parent_id_field
        self._parent_id = parent_id
        self._extra_fields = extra_fields or {}
        self._logger_name = logger_name or f"ascent.{run_type}.{parent_id}"
        self._run_id: uuid.UUID | None = None
        self._logger: logging.Logger | None = None

    def __enter__(self) -> logging.Logger:
        now = datetime.datetime.now(tz=datetime.UTC)

        # Create run record
        session: Session = self._session_factory()
        try:
            run = self._run_model_class(
                **{self._parent_id_field: self._parent_id},
                **self._extra_fields,
                status="RUNNING",
                started_at=now,
            )
            session.add(run)
            session.commit()
            self._run_id = run.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        self._logger = logging.getLogger(self._logger_name)
        return self._logger

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        now = datetime.datetime.now(tz=datetime.UTC)

        # Update run status
        status = "COMPLETED" if exc_type is None else "FAILED"
        error_message = str(exc_val) if exc_val is not None else None

        session: Session = self._session_factory()
        try:
            run = session.get(self._run_model_class, self._run_id)
            if run is not None:
                run.status = status
                run.completed_at = now
                if hasattr(run, "error_message"):
                    run.error_message = error_message
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

        # Don't suppress exceptions
        return False

    @property
    def run_id(self) -> uuid.UUID | None:
        """The ID of the current run record."""
        return self._run_id

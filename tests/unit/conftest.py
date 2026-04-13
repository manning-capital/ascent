"""
Unit test conftest — provides mock infrastructure for all unit tests.
No Docker, no real DB, no network.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from ascent.engine.cache import EngineCache


def pytest_collection_modifyitems(items):
    """Auto-apply 'unit' marker to all tests in this subtree."""
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def mock_db_session():
    """MagicMock(spec=Session) with common query chain patterns pre-configured.

    Supports:
      - session.execute(...).scalar_one_or_none()
      - session.execute(...).scalar_one()
      - session.execute(...).scalar()
      - session.execute(...).unique().scalars().all()
      - session.add() / commit() / refresh() / delete() / flush() / get()
    """
    session = MagicMock(spec=Session)

    # Configure the execute() chain to be chainable
    execute_result = MagicMock()
    session.execute.return_value = execute_result

    unique_result = MagicMock()
    execute_result.unique.return_value = unique_result

    scalars_result = MagicMock()
    unique_result.scalars.return_value = scalars_result

    return session


@pytest.fixture
def mock_cache():
    """MagicMock(spec=EngineCache) — ping() returns True, getters return None."""
    cache = MagicMock(spec=EngineCache)
    cache.ping.return_value = True
    cache.get_feed_data.return_value = None
    cache.get_strategy_state.return_value = None
    cache.is_cache_warm.return_value = False
    return cache

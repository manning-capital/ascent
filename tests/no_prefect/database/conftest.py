"""
Conftest for tests that don't use Prefect.

This conftest provides an auto-use fixture that automatically starts the postgres
test harness without Prefect for all tests in this directory and subdirectories.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine

from ascent.database.testing.utilties import postgres_test_harness


@pytest.fixture(scope="function", autouse=True)
def postgres_engine() -> Generator[Engine, None, None]:
    """
    Auto-use fixture that provides a PostgreSQL engine for each test function.

    This fixture automatically starts a postgres_test_harness without Prefect
    for every test function in this directory and subdirectories.

    Yields:
        Engine: SQLAlchemy engine connected to the test PostgreSQL database
    """
    with postgres_test_harness(use_prefect=False) as engine:
        yield engine

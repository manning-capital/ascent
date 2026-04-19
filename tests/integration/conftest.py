"""
Integration test conftest — provides real Docker infrastructure
(TimescaleDB + Redis) and FastAPI TestClient with dependency overrides.
"""

import pytest
from sqlalchemy.orm import Session

from ascent.database.testing.utilties import ascent_test_harness, clear_database, clear_redis
from ascent.engine.cache import EngineCache
from ascent.server.dependencies import get_cache, get_db
from ascent.server.main import create_app


def pytest_collection_modifyitems(items):
    """Auto-apply 'integration' marker to all tests in this subtree."""
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# ── Infrastructure (session-scoped, started once for all integration tests) ──


@pytest.fixture(scope="session")
def test_env():
    """Start Docker TimescaleDB + Redis via ascent_test_harness().

    Yields AscentTestEnvironment(engine, redis_url, database_url).
    Both containers are torn down after all integration tests complete.
    """
    with ascent_test_harness() as env:
        yield env


@pytest.fixture(scope="session")
def postgres_engine(test_env):
    """SQLAlchemy Engine connected to the test TimescaleDB container."""
    return test_env.engine


@pytest.fixture(scope="session")
def redis_url(test_env):
    """Redis URL for the test Redis container."""
    return test_env.redis_url


@pytest.fixture(scope="session")
def nats_url(test_env):
    """NATS URL for the test NATS JetStream container."""
    return test_env.nats_url


@pytest.fixture(scope="session")
def engine_cache(redis_url):
    """Real EngineCache instance connected to the test Redis container."""
    return EngineCache(redis_url)


# ── Per-test isolation ──


@pytest.fixture(scope="function", autouse=True)
def _reset_db(postgres_engine):
    """Drop + recreate all tables + hypertables before each test."""
    clear_database(postgres_engine)


@pytest.fixture(scope="function", autouse=True)
def _flush_redis(redis_url):
    """FLUSHDB before each test so no stale cache data leaks between tests."""
    clear_redis(redis_url)


@pytest.fixture(scope="function")
def db_session(postgres_engine):
    """Fresh SQLAlchemy Session per test. Closed after test."""
    with Session(postgres_engine) as session:
        yield session


# ── FastAPI app + TestClient ──


@pytest.fixture(scope="function")
def app(postgres_engine, engine_cache):
    """FastAPI app with dependency overrides pointing to test DB + test Redis.

    The lifespan runs _create_tables() which is idempotent — safe to let it run
    since the test harness has already created all tables.
    """
    application = create_app()

    def override_get_db():
        with Session(postgres_engine) as session:
            yield session

    def override_get_cache():
        return engine_cache

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_cache] = override_get_cache

    yield application

    application.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    """TestClient with raise_server_exceptions=False for testing error responses."""
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

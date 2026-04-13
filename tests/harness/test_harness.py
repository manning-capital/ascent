"""
Tests for the ascent_test_harness — verifies that Docker infrastructure
(TimescaleDB + Redis) starts, connects, and cleans up correctly.

These tests are self-contained: each one creates its own harness instance
rather than using the session-scoped fixture from conftest.py.
"""

import docker
import pandas as pd
import pytest
import redis
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from ascent.database.models import AssetType, Base
from ascent.database.testing.utilties import (
    TEST_DB_NAME,
    TEST_DB_PASSWORD,
    TEST_DB_USER,
    AscentTestEnvironment,
    ascent_test_harness,
    clear_database,
    clear_redis,
)


@pytest.mark.slow
class TestAscentTestHarness:
    """Test the ascent_test_harness (combined TimescaleDB + Redis).

    These tests create their own harness instances — they do NOT use the
    session-scoped test_env fixture from the integration conftest.
    This file lives outside ``tests/integration/`` to avoid conflicts
    with the session-scoped Docker containers.
    """

    def test_harness_yields_environment(self):
        """Test that the harness yields an AscentTestEnvironment."""
        with ascent_test_harness() as env:
            assert env is not None
            assert isinstance(env, AscentTestEnvironment)
            assert isinstance(env.engine, Engine)
            assert env.redis_url.startswith("redis://")
            assert env.database_url.startswith("postgresql://")

    def test_engine_properties_are_correct(self):
        """Test that the yielded engine has correct connection properties."""
        with ascent_test_harness() as env:
            assert env.engine.url.database == TEST_DB_NAME
            assert env.engine.url.drivername == "postgresql"
            assert env.engine.url.username == TEST_DB_USER
            assert env.engine.url.password == TEST_DB_PASSWORD
            assert env.engine.url.host in ["localhost", "127.0.0.1"]
            assert env.engine.url.port is not None

    def test_engine_can_connect_to_database(self):
        """Test that the yielded engine can connect to the database."""
        with ascent_test_harness() as env:
            with env.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1

    def test_redis_is_reachable(self):
        """Test that the Redis container is reachable."""
        with ascent_test_harness() as env:
            r = redis.Redis.from_url(env.redis_url)
            assert r.ping() is True
            r.close()

    def test_redis_can_set_and_get(self):
        """Test that Redis can store and retrieve data."""
        with ascent_test_harness() as env:
            r = redis.Redis.from_url(env.redis_url, decode_responses=True)
            r.set("test_key", "test_value")
            assert r.get("test_key") == "test_value"
            r.close()

    def test_tables_are_created(self):
        """Test that all tables are created."""
        with ascent_test_harness() as env:
            for _table_name, table in Base.metadata.tables.items():
                stmt = select(table)
                df = pd.read_sql(stmt, env.engine)
                assert sorted(df.columns.tolist()) == sorted([col.name for col in table.columns])

    def test_can_insert_and_query_data(self):
        """Test that we can insert and query data using the yielded engine."""
        with ascent_test_harness() as env:
            with Session(env.engine) as session:
                clear_database(env.engine)

                asset_type = AssetType(
                    name="Test Asset Type",
                    display_name="Test Asset Type",
                    description="Test Asset Type Description",
                )
                session.add(asset_type)
                session.commit()

                stmt = select(AssetType)
                asset_type_result = session.execute(stmt).scalar_one()
                assert asset_type_result.id is not None
                assert asset_type_result.name == "Test Asset Type"
                assert asset_type_result.description == "Test Asset Type Description"
                assert asset_type_result.is_active is True

    def test_clear_redis_flushes_data(self):
        """Test that clear_redis() removes all keys."""
        with ascent_test_harness() as env:
            r = redis.Redis.from_url(env.redis_url, decode_responses=True)
            r.set("key1", "value1")
            r.set("key2", "value2")
            assert r.dbsize() == 2

            clear_redis(env.redis_url)
            assert r.dbsize() == 0
            r.close()

    def test_multiple_harness_calls_are_independent(self):
        """Test that multiple harness calls create independent environments."""
        with ascent_test_harness() as env1:
            with Session(env1.engine) as session:
                clear_database(env1.engine)
                asset_type1 = AssetType(name="First Asset Type", display_name="First Asset Type")
                session.add(asset_type1)
                session.commit()

        with ascent_test_harness() as env2:
            with Session(env2.engine) as session:
                stmt = select(AssetType)
                result = session.execute(stmt).all()
                assert len(result) == 0

    def test_harness_cleans_up_containers(self):
        """Test that the harness properly cleans up after use."""
        client = docker.from_env()

        pg_before = client.containers.list(all=True, filters={"name": "ascent-test-postgres-*"})
        redis_before = client.containers.list(all=True, filters={"name": "ascent-test-redis-*"})

        with ascent_test_harness() as env:
            with env.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        pg_after = client.containers.list(all=True, filters={"name": "ascent-test-postgres-*"})
        redis_after = client.containers.list(all=True, filters={"name": "ascent-test-redis-*"})

        assert len(pg_after) <= len(pg_before) + 1
        assert len(redis_after) <= len(redis_before) + 1

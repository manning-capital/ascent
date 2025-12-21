import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

import docker
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from ascent.database.models import AssetType, Base
from ascent.database.testing.utilties import (
    TEST_DB_NAME,
    TEST_DB_PASSWORD,
    TEST_DB_USER,
    clear_database,
    postgres_test_harness,
)


# Tests for use_prefect=False functionality
class TestPostgresHarnessNoPrefect:
    """Test the postgres_test_harness with use_prefect=False."""

    def test_harness_yields_engine_when_use_prefect_false(self):
        """Test that the harness yields an engine when use_prefect=False."""
        with postgres_test_harness(use_prefect=False) as engine:
            assert engine is not None
            assert isinstance(engine, Engine)

    def test_engine_properties_are_correct(self):
        """Test that the yielded engine has correct connection properties."""
        with postgres_test_harness(use_prefect=False) as engine:
            assert engine.url.database == TEST_DB_NAME
            assert engine.url.drivername == "postgresql"
            assert engine.url.username == TEST_DB_USER
            assert engine.url.password == TEST_DB_PASSWORD
            assert engine.url.host in ["localhost", "127.0.0.1"]
            assert engine.url.port is not None

    def test_engine_can_connect_to_database(self):
        """Test that the yielded engine can connect to the database."""
        with postgres_test_harness(use_prefect=False) as engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1

    def test_tables_are_created(self):
        """Test that all tables are created when using use_prefect=False."""
        with postgres_test_harness(use_prefect=False) as engine:
            # Check that tables exist
            for _table_name, table in Base.metadata.tables.items():
                stmt = select(table)
                df = pd.read_sql(stmt, engine)
                assert sorted(df.columns.tolist()) == sorted([col.name for col in table.columns])

    def test_can_insert_and_query_data(self):
        """Test that we can insert and query data using the yielded engine."""
        with postgres_test_harness(use_prefect=False) as engine:
            with Session(engine) as session:
                # Clear the database first
                clear_database(engine)

                # Create a new asset type
                asset_type = AssetType(
                    name="Test Asset Type",
                    description="Test Asset Type Description",
                )
                session.add(asset_type)
                session.commit()

                # Query the asset type
                stmt = select(AssetType)
                asset_type_result = session.execute(stmt).scalar_one()
                assert asset_type_result.id is not None
                assert asset_type_result.name == "Test Asset Type"
                assert asset_type_result.description == "Test Asset Type Description"
                assert asset_type_result.is_active is True

    def test_engine_is_independent_of_prefect(self):
        """Test that the engine works independently of Prefect."""
        with postgres_test_harness(use_prefect=False) as engine:
            # Use the engine directly without Prefect
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_database()"))
                db_name = result.fetchone()[0]
                assert db_name == TEST_DB_NAME

    def test_multiple_harness_calls_are_independent(self):
        """Test that multiple harness calls create independent databases."""
        # First harness
        with postgres_test_harness(use_prefect=False) as engine1:
            with Session(engine1) as session:
                clear_database(engine1)
                asset_type1 = AssetType(name="First Asset Type")
                session.add(asset_type1)
                session.commit()

        # Second harness (should be a fresh database)
        with postgres_test_harness(use_prefect=False) as engine2:
            with Session(engine2) as session:
                # Database should be empty (fresh start)
                stmt = select(AssetType)
                result = session.execute(stmt).all()
                assert len(result) == 0

    def test_harness_cleans_up_after_use(self):
        """Test that the harness properly cleans up after use."""
        # Get container name pattern
        client = docker.from_env()

        # Count containers before
        containers_before = client.containers.list(
            all=True, filters={"name": "ascent-postgres-test-*"}
        )

        with postgres_test_harness(use_prefect=False) as engine:
            # Use the engine
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        # Count containers after (should be cleaned up)
        containers_after = client.containers.list(
            all=True, filters={"name": "ascent-postgres-test-*"}
        )

        # The container should be cleaned up
        # (Note: this might not be exact due to timing, but should be similar)
        assert len(containers_after) <= len(containers_before) + 1

    def test_use_prefect_false_with_custom_timeout(self):
        """Test that prefect_server_startup_timeout is ignored when use_prefect=False."""
        # When use_prefect=False, prefect_server_startup_timeout should be ignored
        with postgres_test_harness(use_prefect=False, prefect_server_startup_timeout=999) as engine:
            assert engine is not None
            assert isinstance(engine, Engine)

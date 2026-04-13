import logging
import os
import socket
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import docker
import redis
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

import ascent.database.models as models

LOGGER = logging.getLogger(__name__)

# Test database configuration constants
TEST_DB_USER = "testuser"
TEST_DB_PASSWORD = "testpass"
TEST_DB_NAME = "testdb"
TEST_DB_SIZE_THRESHOLD_MB = 1000

# Docker image defaults (overridable via environment variables)
DEFAULT_TIMESCALEDB_IMAGE = "timescale/timescaledb:latest-pg18"
DEFAULT_REDIS_IMAGE = "redis:8.6.1"


@dataclass
class AscentTestEnvironment:
    """Holds all test infrastructure references."""

    engine: Engine
    redis_url: str
    database_url: str


def _validate_test_database_connection(engine: Engine):
    """
    Validate that the database connection is safe for testing.
    Raises ValueError if the connection appears to be to a production database.
    """
    url = engine.url

    # Check driver
    if url.drivername != "postgresql":
        raise ValueError(
            f"Unsupported database driver: {url.drivername}. Only PostgreSQL is supported."
        )

    # Check host is localhost
    if url.host not in ["localhost", "127.0.0.1"]:
        raise ValueError(
            f"PostgreSQL host '{url.host}' is not localhost. "
            "This may be a production database connection!"
        )

    # Check username matches test user
    if url.username != TEST_DB_USER:
        raise ValueError(
            f"PostgreSQL username '{url.username}' is not the expected test user '{TEST_DB_USER}'. "
            "This may be a production database connection!"
        )

    # Check database name matches test database
    if url.database != TEST_DB_NAME:
        raise ValueError(
            f"PostgreSQL database '{url.database}' is not the expected test database '{TEST_DB_NAME}'. "
            "This may be a production database connection!"
        )

    # Additional check: verify we can connect and it's not a production database
    try:
        with engine.connect() as conn:
            # Check database size - if it's too large, it might be production
            result = conn.execute(
                text("""
                SELECT pg_database_size(current_database()) as size_bytes
            """)
            )
            size_bytes = result.fetchone()[0]
            size_mb = size_bytes / (1024 * 1024)

            if (
                size_mb > TEST_DB_SIZE_THRESHOLD_MB
            ):  # More than the threshold might indicate production data
                raise ValueError(
                    f"Database size ({size_mb:.1f}MB) is suspiciously large for a test database. "
                    "This may be a production database!"
                )

    except Exception as e:
        if "production database" in str(e):
            raise
        # If we can't connect or query, that's also suspicious
        raise ValueError(f"Cannot validate database safety: {e}") from e


def clear_database(engine: Engine):
    """
    Clear the database of all data.
    Performs safety checks to ensure we're not clearing a production database.
    """

    # Validate that this is a safe test database connection
    _validate_test_database_connection(engine)

    # Drop all tables in the database.
    models.Base.metadata.drop_all(engine)

    # Create all tables in the database.
    models.Base.metadata.create_all(engine)

    # Convert attribute tables to TimescaleDB hypertables (daily chunks)
    from ascent.database.setup import ensure_hypertables

    ensure_hypertables(engine)


def clear_redis(redis_url: str):
    """
    Flush all keys from the test Redis database.
    Mirrors clear_database() for Redis-side isolation between tests.
    """
    r = redis.Redis.from_url(redis_url)
    r.flushdb()
    r.close()


def _cleanup_old_test_containers():
    """
    Clean up any old test containers that may have been left behind.
    Removes containers matching ascent-test-postgres-* and ascent-test-redis-*.
    """
    try:
        client = docker.from_env()

        for pattern in ["ascent-test-postgres-*", "ascent-test-redis-*"]:
            test_containers = client.containers.list(
                all=True,
                filters={"name": pattern},
            )

            if test_containers:
                LOGGER.info(
                    f"Found {len(test_containers)} old test containers matching '{pattern}' to clean up"
                )

                for container in test_containers:
                    try:
                        container_name = container.name
                        LOGGER.info(f"Cleaning up old test container: {container_name}")

                        if container.status == "running":
                            container.stop(timeout=5)
                            LOGGER.info(f"Stopped container: {container_name}")

                        container.remove()
                        LOGGER.info(f"Removed container: {container_name}")

                    except Exception as e:
                        LOGGER.warning(f"Failed to clean up container {container.name}: {e}")

    except Exception as e:
        LOGGER.warning(f"Failed to clean up old test containers: {e}")


def _cleanup_old_test_volumes():
    """
    Clean up any old test volumes that may have been left behind.
    Removes volumes matching ascent-test-postgres-*.
    """
    try:
        client = docker.from_env()

        test_volumes = client.volumes.list(filters={"name": "ascent-test-postgres-*"})

        if test_volumes:
            LOGGER.info(f"Found {len(test_volumes)} old test volumes to clean up")

            for volume in test_volumes:
                try:
                    volume_name = volume.name
                    LOGGER.info(f"Cleaning up old test volume: {volume_name}")

                    volume.remove()
                    LOGGER.info(f"Removed volume: {volume_name}")

                except Exception as e:
                    LOGGER.warning(f"Failed to clean up volume {volume.name}: {e}")
        else:
            LOGGER.info("No old test volumes found to clean up")

    except Exception as e:
        LOGGER.warning(f"Failed to clean up old test volumes: {e}")


def _find_free_port():
    """
    Find a free port on localhost.
    Uses a more robust approach to avoid race conditions.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def _wait_for_postgres(
    host: str, port: int, user: str, password: str, database: str, timeout: int = 30
):
    """Wait for PostgreSQL to be ready."""
    LOGGER.info(f"Waiting for PostgreSQL to be ready on {host}:{port}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            test_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            test_engine = create_engine(test_url)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            LOGGER.info("PostgreSQL is ready!")
            return True
        except OperationalError:
            time.sleep(1)

    raise TimeoutError(f"PostgreSQL did not become ready within {timeout} seconds")


def _wait_for_redis(redis_url: str, timeout: int = 10):
    """Wait for Redis to be ready."""
    LOGGER.info(f"Waiting for Redis to be ready at {redis_url}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            r = redis.Redis.from_url(redis_url)
            r.ping()
            r.close()
            LOGGER.info("Redis is ready!")
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            time.sleep(0.5)

    raise TimeoutError(f"Redis did not become ready within {timeout} seconds")


@contextmanager
def ascent_test_harness() -> Generator[AscentTestEnvironment, None, None]:
    """
    Start all Docker infrastructure needed for Ascent integration tests.

    Manages two containers:
      1. TimescaleDB (default: timescale/timescaledb:latest-pg18) — PostgreSQL + hypertables
      2. Redis (default: redis:8.6.1) — cache layer

    Environment variable overrides:
      - ASCENT_TEST_TIMESCALEDB_IMAGE — TimescaleDB Docker image
      - ASCENT_TEST_REDIS_IMAGE — Redis Docker image

    Lifecycle:
      1. Cleanup old ascent-test-* containers and volumes
      2. Find free ports for both services
      3. Start both containers
      4. Wait for readiness (Postgres via SQL ping, Redis via PING command)
      5. Create TimescaleDB extension + all tables + hypertables
      6. Validate safety (localhost, testuser, testdb, size < 1GB)
      7. Yield AscentTestEnvironment(engine, redis_url, database_url)
      8. Teardown: drop tables, stop + remove both containers, remove volume

    Yields:
        AscentTestEnvironment with engine, redis_url, and database_url.

    Example::

        with ascent_test_harness() as env:
            with Session(env.engine) as session:
                ...
            cache = EngineCache(env.redis_url)
            cache.ping()
    """
    # Resolve Docker images (environment overrides take precedence)
    timescaledb_image = os.environ.get("ASCENT_TEST_TIMESCALEDB_IMAGE", DEFAULT_TIMESCALEDB_IMAGE)
    redis_image = os.environ.get("ASCENT_TEST_REDIS_IMAGE", DEFAULT_REDIS_IMAGE)

    # Clean up any old test containers and volumes first
    LOGGER.info("Cleaning up any old test containers and volumes...")
    _cleanup_old_test_containers()
    _cleanup_old_test_volumes()

    # Generate unique names with distinctive prefix
    unique_id = uuid.uuid4().hex[:8]

    # --- Postgres configuration ---
    pg_container_name = f"ascent-test-postgres-{unique_id}"
    pg_volume_name = f"ascent-test-postgres-{unique_id}"
    pg_port = _find_free_port()

    # --- Redis configuration ---
    redis_container_name = f"ascent-test-redis-{unique_id}"
    redis_port = _find_free_port()

    # Database configuration
    db_user = TEST_DB_USER
    db_password = TEST_DB_PASSWORD
    db_name = TEST_DB_NAME

    LOGGER.info(f"Using port {pg_port} for PostgreSQL container")
    LOGGER.info(f"Using port {redis_port} for Redis container")

    # Initialize Docker client
    try:
        client = docker.from_env()
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize Docker client: {e}\n"
            "Please ensure Docker is running. You can start Docker Desktop or run:\n"
            "  docker --version  # to check if Docker is installed\n"
            "  docker ps         # to check if Docker daemon is running\n"
            "If Docker is not available, you may need to install Docker Desktop or start the Docker daemon."
        ) from e

    pg_container = None
    redis_container = None
    pg_volume = None
    engine = None

    try:
        # --- Start PostgreSQL/TimescaleDB container ---
        LOGGER.info(
            f"Starting TimescaleDB container '{pg_container_name}' with image {timescaledb_image}..."
        )
        pg_container = client.containers.run(
            timescaledb_image,
            name=pg_container_name,
            environment={
                "POSTGRES_USER": db_user,
                "POSTGRES_PASSWORD": db_password,
                "POSTGRES_DB": db_name,
            },
            ports={5432: pg_port},
            volumes={pg_volume_name: {"bind": "/var/lib/postgresql", "mode": "rw"}},
            detach=True,
            remove=False,
        )
        pg_volume = client.volumes.get(pg_volume_name)

        # --- Start Redis container ---
        LOGGER.info(
            f"Starting Redis container '{redis_container_name}' with image {redis_image}..."
        )
        redis_container = client.containers.run(
            redis_image,
            name=redis_container_name,
            ports={6379: redis_port},
            detach=True,
            remove=False,
        )

        # --- Wait for both services to be ready ---
        _wait_for_postgres("localhost", pg_port, db_user, db_password, db_name)

        redis_url = f"redis://localhost:{redis_port}/0"
        _wait_for_redis(redis_url)

        # --- Verify PostgreSQL container identity ---
        LOGGER.info("Verifying PostgreSQL container is our test instance...")
        try:
            container_info = pg_container.attrs
            container_env = container_info.get("Config", {}).get("Env", [])

            env_dict = {}
            for env_var in container_env:
                if "=" in env_var:
                    key, value = env_var.split("=", 1)
                    env_dict[key] = value

            if env_dict.get("POSTGRES_USER") != db_user:
                raise ValueError(
                    f"Container POSTGRES_USER mismatch: expected {db_user}, got {env_dict.get('POSTGRES_USER')}"
                )
            if env_dict.get("POSTGRES_DB") != db_name:
                raise ValueError(
                    f"Container POSTGRES_DB mismatch: expected {db_name}, got {env_dict.get('POSTGRES_DB')}"
                )

            LOGGER.info("Container verification passed - confirmed test instance")
        except Exception as e:
            raise ValueError(f"Failed to verify container safety: {e}") from e

        # --- Set up PostgreSQL: engine, tables, hypertables ---
        database_url = f"postgresql://{db_user}:{db_password}@localhost:{pg_port}/{db_name}"
        LOGGER.info(f"Database URL: postgresql://{db_user}:***@localhost:{pg_port}/{db_name}")
        engine = create_engine(database_url)

        LOGGER.info("Validating database connection safety...")
        _validate_test_database_connection(engine)
        LOGGER.info("Database connection validation passed - safe for testing")

        LOGGER.info("Enabling TimescaleDB extension...")
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            conn.commit()

        LOGGER.info("Creating all tables in the database...")
        models.Base.metadata.create_all(engine)

        from ascent.database.setup import ensure_hypertables

        ensure_hypertables(engine)

        LOGGER.info("Verifying Redis connectivity...")
        r = redis.Redis.from_url(redis_url)
        r.ping()
        r.close()
        LOGGER.info("Redis connectivity verified")

        yield AscentTestEnvironment(
            engine=engine,
            redis_url=redis_url,
            database_url=database_url,
        )

    finally:
        # Clean-up the database (only if engine was created successfully)
        if engine:
            try:
                LOGGER.info("Dropping all tables...")
                models.Base.metadata.drop_all(engine)
            except Exception as e:
                LOGGER.warning(f"Error dropping tables: {e}")

        # Clean up the Redis container
        if redis_container:
            try:
                LOGGER.info(f"Stopping Redis container '{redis_container_name}'...")
                redis_container.stop(timeout=5)
                LOGGER.info(f"Removing Redis container '{redis_container_name}'...")
                redis_container.remove()
            except Exception as e:
                LOGGER.warning(f"Error cleaning up Redis container: {e}")

        # Clean up the PostgreSQL container
        if pg_container:
            try:
                LOGGER.info(f"Stopping PostgreSQL container '{pg_container_name}'...")
                pg_container.stop(timeout=10)
                LOGGER.info(f"Removing PostgreSQL container '{pg_container_name}'...")
                pg_container.remove()
            except Exception as e:
                LOGGER.warning(f"Error cleaning up PostgreSQL container: {e}")

        # Clean up the named volume
        if pg_volume:
            try:
                LOGGER.info(f"Removing PostgreSQL volume '{pg_volume_name}'...")
                pg_volume.remove()
            except Exception as e:
                LOGGER.warning(f"Error cleaning up volume: {e}")

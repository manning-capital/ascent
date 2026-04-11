"""Database setup utilities for TimescaleDB hypertable configuration."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Attribute tables to convert to TimescaleDB hypertables with daily partitioning.
_HYPERTABLE_TABLES = (
    "instrument_attribute",
    "instrument_period_attribute",
    "composite_attribute",
    "composite_period_attribute",
)


def ensure_hypertables(engine: Engine) -> None:
    """Convert attribute tables to TimescaleDB hypertables (daily chunks).

    Safe to call on every startup — ``if_not_exists`` makes this idempotent.
    """
    with engine.connect() as conn:
        for tbl in _HYPERTABLE_TABLES:
            conn.execute(
                text(
                    f"SELECT create_hypertable('{tbl}', 'timestamp', "
                    f"chunk_time_interval => INTERVAL '1 day', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
        conn.commit()

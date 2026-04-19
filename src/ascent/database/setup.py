"""Database setup utilities for TimescaleDB hypertable configuration."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Tables to convert to TimescaleDB hypertables with daily partitioning.
# Each entry is (table_name, partitioning_column).
_HYPERTABLE_TABLES = (
    ("instrument_attribute", "timestamp"),
    ("instrument_period_attribute", "timestamp"),
    ("composite_attribute", "timestamp"),
    ("composite_period_attribute", "timestamp"),
    ("event_outbox", "created_at"),
)


def ensure_hypertables(engine: Engine) -> None:
    """Convert selected tables to TimescaleDB hypertables (daily chunks).

    Safe to call on every startup — ``if_not_exists`` makes this idempotent.
    """
    with engine.connect() as conn:
        for tbl, col in _HYPERTABLE_TABLES:
            conn.execute(
                text(
                    f"SELECT create_hypertable('{tbl}', '{col}', "
                    f"chunk_time_interval => INTERVAL '1 day', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
        conn.commit()

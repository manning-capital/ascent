"""TimescaleDB-backed :class:`ascent.ports.HistoricalFeedStore`.

Upserts feed output DataFrames into their mapped EAV hypertables using
``INSERT ... ON CONFLICT (timestamp, ...) DO UPDATE``. The partition key
is the row timestamp, which matches both TimescaleDB's hypertable shape
and the domain's "upsert by timestamp" requirement.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

import pandas as pd
from sqlalchemy import MetaData, Table, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class TimescaleFeedStore:
    """Upsert + range-query over feed EAV tables."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._sf = session_factory
        self._tables: dict[str, Table] = {}
        self._metadata = MetaData()

    async def upsert(self, feed_id: uuid.UUID, output_table: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        return await asyncio.to_thread(self._upsert_sync, output_table, df)

    async def get_range(
        self,
        feed_id: uuid.UUID,
        output_table: str,
        *,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        return await asyncio.to_thread(self._get_range_sync, output_table, start, end)

    # ---- sync internals ----

    def _upsert_sync(self, output_table: str, df: pd.DataFrame) -> int:
        bind = self._sf.kw["bind"]
        table = self._reflect(output_table, bind)
        pk_cols = [c.name for c in table.primary_key.columns]
        if not pk_cols:
            # Fall back to append if there's no PK to conflict on.
            df.to_sql(output_table, con=bind, if_exists="append", index=False, method="multi")
            return len(df)

        records = df.to_dict(orient="records")
        stmt = insert(table).values(records)
        non_pk = [c.name for c in table.columns if c.name not in pk_cols]
        update_map = {col: getattr(stmt.excluded, col) for col in non_pk}
        if update_map:
            stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_map)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
        with bind.begin() as conn:
            conn.execute(stmt)
        return len(records)

    def _get_range_sync(self, output_table: str, start: datetime, end: datetime) -> pd.DataFrame:
        bind = self._sf.kw["bind"]
        query = text(
            f"SELECT * FROM {output_table} "
            "WHERE timestamp >= :start AND timestamp < :end "
            "ORDER BY timestamp ASC"
        )
        with bind.connect() as conn:
            return pd.read_sql(query, conn, params={"start": start, "end": end})

    def _reflect(self, table_name: str, bind) -> Table:
        if table_name not in self._tables:
            self._tables[table_name] = Table(table_name, self._metadata, autoload_with=bind)
        return self._tables[table_name]

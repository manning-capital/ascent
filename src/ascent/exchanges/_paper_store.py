"""SQLite-backed ledger for :class:`PaperExchange`.

Persists balances and order records so that restarting an Ascent process
doesn't wipe what the strategy already executed against the paper venue.
Balances are stored as signed ``Decimal`` (text-encoded to avoid float
drift); a negative balance represents a short position.

The store is intentionally minimal — two tables, no migrations, no cross
connection coordination. One :class:`PaperExchange` instance owns one
:class:`_PaperStore`.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class StoredOrder:
    exchange_order_id: str
    status: str
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    client_order_id: str | None
    error_message: str | None


class _PaperStore:
    """Thread-safe SQLite-backed paper ledger."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    @property
    def path(self) -> str:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_balance (
                    asset_symbol TEXT PRIMARY KEY,
                    total TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_order (
                    exchange_order_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    filled_quantity TEXT NOT NULL,
                    average_fill_price TEXT,
                    client_order_id TEXT,
                    error_message TEXT
                )
                """
            )

    # ------------------------------------------------------------------
    # Balances
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        with self._lock:
            (count,) = self._conn.execute("SELECT COUNT(*) FROM paper_balance").fetchone()
            return count == 0

    def seed_balances(self, balances: dict[str, Decimal]) -> None:
        """Insert balances. Used for one-time bootstrap from config; existing
        rows are left untouched (config doesn't override live state).
        """
        with self._lock, self._conn:
            for symbol, total in balances.items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO paper_balance(asset_symbol, total) VALUES (?, ?)",
                    (symbol, str(total)),
                )

    def get_balance(self, asset_symbol: str) -> Decimal:
        with self._lock:
            row = self._conn.execute(
                "SELECT total FROM paper_balance WHERE asset_symbol = ?",
                (asset_symbol,),
            ).fetchone()
            return Decimal(row[0]) if row else Decimal("0")

    def all_balances(self) -> dict[str, Decimal]:
        with self._lock:
            rows = self._conn.execute("SELECT asset_symbol, total FROM paper_balance").fetchall()
            return {symbol: Decimal(total) for symbol, total in rows}

    def adjust_balance(self, asset_symbol: str, delta: Decimal) -> Decimal:
        """Atomic signed adjustment. Returns the new balance."""
        with self._lock, self._conn:
            current = self.get_balance(asset_symbol)
            new_total = current + delta
            self._conn.execute(
                """
                INSERT INTO paper_balance(asset_symbol, total) VALUES (?, ?)
                ON CONFLICT(asset_symbol) DO UPDATE SET total = excluded.total
                """,
                (asset_symbol, str(new_total)),
            )
            return new_total

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def upsert_order(self, order: StoredOrder) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO paper_order(
                    exchange_order_id, status, filled_quantity, average_fill_price,
                    client_order_id, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange_order_id) DO UPDATE SET
                    status = excluded.status,
                    filled_quantity = excluded.filled_quantity,
                    average_fill_price = excluded.average_fill_price,
                    client_order_id = excluded.client_order_id,
                    error_message = excluded.error_message
                """,
                (
                    order.exchange_order_id,
                    order.status,
                    str(order.filled_quantity),
                    None if order.average_fill_price is None else str(order.average_fill_price),
                    order.client_order_id,
                    order.error_message,
                ),
            )

    def get_order(self, exchange_order_id: str) -> StoredOrder | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT exchange_order_id, status, filled_quantity, average_fill_price,
                       client_order_id, error_message
                FROM paper_order WHERE exchange_order_id = ?
                """,
                (exchange_order_id,),
            ).fetchone()
            return _row_to_order(row) if row else None

    def get_order_by_client_id(self, client_order_id: str) -> StoredOrder | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT exchange_order_id, status, filled_quantity, average_fill_price,
                       client_order_id, error_message
                FROM paper_order WHERE client_order_id = ?
                """,
                (client_order_id,),
            ).fetchone()
            return _row_to_order(row) if row else None


def _row_to_order(row: tuple) -> StoredOrder:
    return StoredOrder(
        exchange_order_id=row[0],
        status=row[1],
        filled_quantity=Decimal(row[2]),
        average_fill_price=Decimal(row[3]) if row[3] is not None else None,
        client_order_id=row[4],
        error_message=row[5],
    )

"""Paper (simulated) exchange for backtesting and paper trading.

Orders fill instantly at the requested price with no slippage. Balances
are tracked in a SQLite-backed signed-:class:`Decimal` ledger that
survives process restarts, so a reconciliation pass after a restart sees
the same balances the strategy left behind.

Signed balances mean shorts. A SELL fill that takes ``BTC`` below zero is
allowed and represents a short position — effectively a no-cost-to-borrow
margin simulation. The repository's strategies (e.g. OU pairs trading)
need to settle short legs somewhere; the paper exchange does that here so
end-to-end tests don't need a separate margin venue.

Configuration::

    {
        "db_path": "/abs/path/to/paper.sqlite",   # default: ~/.ascent/paper-exchange.sqlite
        "balances": [                              # one-time bootstrap; ignored if db_path exists
            {"asset_symbol": "USD", "total": 100000},
            {"asset_symbol": "BTC", "total": 0}
        ]
    }
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

from ascent.exchanges._paper_store import StoredOrder, _PaperStore
from ascent.exchanges.base import (
    BalanceEntry,
    BaseExchange,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)


class PaperExchange(BaseExchange):
    """Simulated exchange that fills orders instantly at the requested price."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._store = _PaperStore(self._resolve_db_path())
        if self._store.is_empty():
            self._seed_initial_balances()

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        if request.from_asset_symbol is None or request.to_asset_symbol is None:
            return _reject(
                "PaperExchange requires from_asset_symbol and to_asset_symbol on OrderRequest"
            )
        if request.price is None or request.price <= 0:
            return _reject("PaperExchange requires a non-zero price on every order")

        quantity = Decimal(str(request.quantity))
        price = Decimal(str(request.price))
        notional = quantity * price

        side = request.side.upper()
        if side == "BUY":
            self._store.adjust_balance(request.from_asset_symbol, quantity)
            self._store.adjust_balance(request.to_asset_symbol, -notional)
        elif side == "SELL":
            self._store.adjust_balance(request.from_asset_symbol, -quantity)
            self._store.adjust_balance(request.to_asset_symbol, notional)
        else:
            return _reject(f"Unknown order side '{request.side}'")

        exchange_order_id = str(uuid.uuid4())
        stored = StoredOrder(
            exchange_order_id=exchange_order_id,
            status="FILLED",
            filled_quantity=quantity,
            average_fill_price=price,
            client_order_id=request.client_order_id,
            error_message=None,
        )
        self._store.upsert_order(stored)
        return OrderResponse(
            exchange_order_id=exchange_order_id,
            status="FILLED",
            filled_quantity=float(quantity),
            average_fill_price=float(price),
        )

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        existing = self._store.get_order(exchange_order_id)
        if existing is None:
            return OrderResponse(
                exchange_order_id=exchange_order_id,
                status="REJECTED",
                error_message=f"Order {exchange_order_id} not found",
            )
        if existing.status == "FILLED":
            return OrderResponse(
                exchange_order_id=exchange_order_id,
                status="REJECTED",
                filled_quantity=float(existing.filled_quantity),
                average_fill_price=(
                    float(existing.average_fill_price)
                    if existing.average_fill_price is not None
                    else None
                ),
                error_message="Cannot cancel a filled order",
            )
        cancelled = StoredOrder(
            exchange_order_id=existing.exchange_order_id,
            status="CANCELLED",
            filled_quantity=existing.filled_quantity,
            average_fill_price=existing.average_fill_price,
            client_order_id=existing.client_order_id,
            error_message=None,
        )
        self._store.upsert_order(cancelled)
        return OrderResponse(exchange_order_id=exchange_order_id, status="CANCELLED")

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        existing = self._store.get_order(exchange_order_id)
        if existing is None:
            return OrderStatusResponse(
                exchange_order_id=exchange_order_id,
                status="NOT_FOUND",
            )
        return _stored_to_status(existing)

    def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None:
        existing = self._store.get_order_by_client_id(client_order_id)
        if existing is None:
            return None
        return _stored_to_status(existing)

    def get_balances(self) -> list[BalanceEntry]:
        balances = self._store.all_balances()
        return [
            BalanceEntry(
                asset_symbol=symbol,
                available=float(total),
                reserved=0.0,
                total=float(total),
            )
            for symbol, total in sorted(balances.items())
        ]

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _resolve_db_path(self) -> str:
        configured = self.config.get("db_path")
        if configured:
            return configured
        default_dir = os.path.expanduser("~/.ascent")
        os.makedirs(default_dir, exist_ok=True)
        return os.path.join(default_dir, "paper-exchange.sqlite")

    def _seed_initial_balances(self) -> None:
        seeded = self.config.get("balances", [])
        if not seeded:
            return
        normalized: dict[str, Decimal] = {}
        for entry in seeded:
            if isinstance(entry, dict):
                symbol = entry.get("asset_symbol")
                total = entry.get("total", entry.get("available", 0))
            else:
                symbol = getattr(entry, "asset_symbol", None)
                total = getattr(entry, "total", getattr(entry, "available", 0))
            if symbol is None:
                continue
            normalized[symbol] = Decimal(str(total))
        if normalized:
            self._store.seed_balances(normalized)


def _reject(message: str) -> OrderResponse:
    return OrderResponse(
        exchange_order_id="",
        status="REJECTED",
        error_message=message,
    )


def _stored_to_status(stored: StoredOrder) -> OrderStatusResponse:
    return OrderStatusResponse(
        exchange_order_id=stored.exchange_order_id,
        status=stored.status,
        filled_quantity=float(stored.filled_quantity),
        average_fill_price=(
            float(stored.average_fill_price) if stored.average_fill_price is not None else None
        ),
        error_message=stored.error_message,
    )

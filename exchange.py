"""Sample exchange that simulates trading Kraken securities.

Orders go through a realistic async lifecycle (SUBMITTED → PARTIALLY_FILLED →
FILLED).  Fill schedules are pre-computed at submission time and evaluated
lazily when the runner polls ``get_open_orders()``.  No background threads
are needed inside the exchange itself — the runner's monitor loop drives
status updates.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from ascent.exchanges.base import (
    BalanceEntry,
    BaseExchange,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)

logger = logging.getLogger(__name__)


class KrakenSecurityExchange(BaseExchange):
    """Paper exchange that simulates Kraken security trades."""

    provider = "KRAKEN"
    instrument_type = "SPOT_INSTRUMENT"
    poll_interval = 1.0

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._balances: dict[str, float] = {"USD": self.config.get("initial_balance", 100000.0)}
        self._orders: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    # ------------------------------------------------------------------
    # Fill schedule helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_schedule(quantity: float) -> list[tuple[float, float]]:
        """Pre-compute a random fill schedule.

        Returns a sorted list of ``(time_offset_seconds, fill_size)`` tuples.
        Total fill sizes sum to *quantity*; total time is 1–60 seconds.
        """
        num_fills = random.randint(1, 5)
        total_duration = random.uniform(1.0, 60.0)

        fill_times = sorted(random.uniform(0, total_duration) for _ in range(num_fills))

        raw = [random.random() for _ in range(num_fills)]
        total = sum(raw)
        fill_sizes = [r / total * quantity for r in raw]
        # Snap last fill to avoid floating-point drift
        fill_sizes[-1] = quantity - sum(fill_sizes[:-1])

        return list(zip(fill_times, fill_sizes, strict=False))

    def _evaluate_fills(self, order: dict[str, Any]) -> None:
        """Update an order's fill state based on elapsed time.

        When every scheduled fill has passed, snap directly to the order's
        total quantity — re-summing the schedule fragments here would
        re-introduce the float drift that ``_build_schedule`` already
        snapped out, leaving orders stuck on PARTIALLY_FILLED with
        ``filled_quantity=0.00999...`` forever.
        """
        elapsed = time.monotonic() - order["start_time"]
        schedule = order["schedule"]
        total = order["request"].quantity

        if schedule and elapsed >= schedule[-1][0]:
            order["filled_quantity"] = total
            order["status"] = "FILLED"
            return

        filled = sum(size for t, size in schedule if elapsed >= t)
        if filled > 0:
            order["filled_quantity"] = filled
            order["status"] = "PARTIALLY_FILLED"

    # ------------------------------------------------------------------
    # Core order lifecycle
    # ------------------------------------------------------------------

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        order_id = f"SIM-{self._next_id:06d}"
        self._next_id += 1

        fill_price = request.price or 100.0
        self._orders[order_id] = {
            "request": request,
            "status": "SUBMITTED",
            "filled_quantity": 0.0,
            "fill_price": fill_price,
            "schedule": self._build_schedule(request.quantity),
            "start_time": time.monotonic(),
        }

        logger.info(
            "SUBMITTED %s %s %s/%s qty=%.4f @ %.2f",
            order_id,
            request.side,
            request.from_asset_symbol,
            request.to_asset_symbol,
            request.quantity,
            fill_price,
        )

        return OrderResponse(
            exchange_order_id=order_id,
            status="SUBMITTED",
        )

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        order = self._orders.get(exchange_order_id)
        if not order:
            return OrderResponse(
                exchange_order_id=exchange_order_id,
                status="NOT_FOUND",
                error_message=f"Order {exchange_order_id} not found",
            )
        self._evaluate_fills(order)
        if order["status"] == "FILLED":
            return OrderResponse(
                exchange_order_id=exchange_order_id,
                status="FILLED",
                error_message="Cannot cancel a fully filled order",
            )
        order["status"] = "CANCELLED"
        return OrderResponse(
            exchange_order_id=exchange_order_id,
            status="CANCELLED",
            filled_quantity=order["filled_quantity"],
            average_fill_price=order["fill_price"] if order["filled_quantity"] > 0 else None,
        )

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        order = self._orders.get(exchange_order_id)
        if not order:
            return OrderStatusResponse(
                exchange_order_id=exchange_order_id,
                status="NOT_FOUND",
                error_message=f"Order {exchange_order_id} not found",
            )
        if order["status"] not in ("FILLED", "CANCELLED"):
            self._evaluate_fills(order)
        return OrderStatusResponse(
            exchange_order_id=exchange_order_id,
            status=order["status"],
            filled_quantity=order["filled_quantity"],
            average_fill_price=order["fill_price"] if order["filled_quantity"] > 0 else None,
        )

    def get_balances(self) -> list[BalanceEntry]:
        return [
            BalanceEntry(asset_symbol=sym, available=amt, total=amt)
            for sym, amt in self._balances.items()
        ]

    def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None:
        for order_id, order in self._orders.items():
            if order["request"].client_order_id == client_order_id:
                if order["status"] not in ("FILLED", "CANCELLED"):
                    self._evaluate_fills(order)
                return OrderStatusResponse(
                    exchange_order_id=order_id,
                    status=order["status"],
                    filled_quantity=order["filled_quantity"],
                    average_fill_price=order["fill_price"]
                    if order["filled_quantity"] > 0
                    else None,
                )
        return None

    # ------------------------------------------------------------------
    # Polling-based monitoring
    # ------------------------------------------------------------------

    def get_open_orders(self) -> list[OrderStatusResponse]:
        results = []
        for order_id, order in self._orders.items():
            if order["status"] in ("FILLED", "CANCELLED"):
                continue
            self._evaluate_fills(order)
            results.append(
                OrderStatusResponse(
                    exchange_order_id=order_id,
                    status=order["status"],
                    filled_quantity=order["filled_quantity"],
                    average_fill_price=order["fill_price"]
                    if order["filled_quantity"] > 0
                    else None,
                )
            )
        return results


if __name__ == "__main__":
    KrakenSecurityExchange.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )

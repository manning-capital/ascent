"""Sample exchange that simulates trading Kraken securities."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

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
    instrument_type = "SECURITY"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._balances: dict[str, float] = {"USD": self.config.get("initial_balance", 100000.0)}
        self._orders: dict[str, dict] = {}
        self._next_id = 1

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        order_id = f"SIM-{self._next_id:06d}"
        self._next_id += 1

        # Simulate immediate fill at requested price
        fill_price = request.price or 100.0
        self._orders[order_id] = {
            "request": request,
            "status": "FILLED",
            "filled_quantity": request.quantity,
            "fill_price": fill_price,
        }

        logger.info(
            "FILLED %s %s %s/%s qty=%.4f @ %.2f",
            order_id,
            request.side,
            request.from_asset_symbol,
            request.to_asset_symbol,
            request.quantity,
            fill_price,
        )

        return OrderResponse(
            exchange_order_id=order_id,
            status="FILLED",
            filled_quantity=request.quantity,
            average_fill_price=fill_price,
        )

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        order = self._orders.get(exchange_order_id)
        if not order:
            return OrderResponse(
                exchange_order_id=exchange_order_id,
                status="NOT_FOUND",
                error_message=f"Order {exchange_order_id} not found",
            )
        order["status"] = "CANCELLED"
        return OrderResponse(exchange_order_id=exchange_order_id, status="CANCELLED")

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        order = self._orders.get(exchange_order_id)
        if not order:
            return OrderStatusResponse(
                exchange_order_id=exchange_order_id,
                status="NOT_FOUND",
                error_message=f"Order {exchange_order_id} not found",
            )
        return OrderStatusResponse(
            exchange_order_id=exchange_order_id,
            status=order["status"],
            filled_quantity=order.get("filled_quantity", 0.0),
            average_fill_price=order.get("fill_price"),
        )

    def get_balances(self) -> list[BalanceEntry]:
        return [
            BalanceEntry(asset_symbol=sym, available=amt, total=amt)
            for sym, amt in self._balances.items()
        ]


if __name__ == "__main__":
    load_dotenv()
    KrakenSecurityExchange.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )

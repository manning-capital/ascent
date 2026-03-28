"""Paper (simulated) exchange for backtesting and paper trading.

Orders are filled immediately at the requested price with no slippage.
This serves both as the default paper trading venue and as a reference
implementation for users building their own exchange integrations.
"""

from __future__ import annotations

import uuid

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
        # Internal order book keyed by exchange_order_id
        self._orders: dict[str, OrderResponse] = {}

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        exchange_order_id = str(uuid.uuid4())
        response = OrderResponse(
            exchange_order_id=exchange_order_id,
            status="FILLED",
            filled_quantity=request.quantity,
            average_fill_price=request.price,
        )
        self._orders[exchange_order_id] = response
        return response

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        existing = self._orders.get(exchange_order_id)
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
                filled_quantity=existing.filled_quantity,
                average_fill_price=existing.average_fill_price,
                error_message="Cannot cancel a filled order",
            )
        response = OrderResponse(
            exchange_order_id=exchange_order_id,
            status="CANCELLED",
        )
        self._orders[exchange_order_id] = response
        return response

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        existing = self._orders.get(exchange_order_id)
        if existing is None:
            return OrderStatusResponse(
                exchange_order_id=exchange_order_id,
                status="REJECTED",
                error_message=f"Order {exchange_order_id} not found",
            )
        return OrderStatusResponse(
            exchange_order_id=exchange_order_id,
            status=existing.status,
            filled_quantity=existing.filled_quantity,
            average_fill_price=existing.average_fill_price,
        )

    def get_balances(self) -> list[BalanceEntry]:
        balances = self.config.get("balances", [])
        return [BalanceEntry.model_validate(b) for b in balances]

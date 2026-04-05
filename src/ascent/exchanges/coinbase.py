"""Coinbase spot exchange integration for crypto instruments.

Implements the BaseExchange interface for submitting and managing orders
on the Coinbase Advanced Trade API.  The ``config`` dict should contain
API credentials and any Coinbase-specific settings.

Example config::

    {
        "api_key": "...",
        "api_secret": "...",
        "base_url": "https://api.coinbase.com",
    }
"""

from __future__ import annotations

from ascent.exchanges.base import (
    BalanceEntry,
    BaseExchange,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)


class CoinbaseSpotExchange(BaseExchange):
    """Coinbase spot market exchange for crypto instrument pairs."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.base_url = self.config.get("base_url", "https://api.coinbase.com")
        self._api_key = self.config.get("api_key", "")
        self._api_secret = self.config.get("api_secret", "")

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        raise NotImplementedError("Coinbase spot order submission not yet implemented")

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        raise NotImplementedError("Coinbase spot order cancellation not yet implemented")

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        raise NotImplementedError("Coinbase spot order status not yet implemented")

    def get_balances(self) -> list[BalanceEntry]:
        raise NotImplementedError("Coinbase spot balance retrieval not yet implemented")

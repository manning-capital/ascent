"""Kraken spot exchange integration for crypto instruments.

Implements the BaseExchange interface for submitting and managing orders
on the Kraken spot market.  The ``config`` dict should contain API
credentials and any Kraken-specific settings (e.g. tier-based rate
limits).

Example config::

    {
        "api_key": "...",
        "api_secret": "...",
        "base_url": "https://api.kraken.com",
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


class KrakenSpotExchange(BaseExchange):
    """Kraken spot market exchange for crypto instrument pairs."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.base_url = self.config.get("base_url", "https://api.kraken.com")
        self._api_key = self.config.get("api_key", "")
        self._api_secret = self.config.get("api_secret", "")

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        raise NotImplementedError("Kraken spot order submission not yet implemented")

    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        raise NotImplementedError("Kraken spot order cancellation not yet implemented")

    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        raise NotImplementedError("Kraken spot order status not yet implemented")

    def get_balances(self) -> list[BalanceEntry]:
        raise NotImplementedError("Kraken spot balance retrieval not yet implemented")

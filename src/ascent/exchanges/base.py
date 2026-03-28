"""Abstract base class for all Ascent exchange integrations.

Every exchange integration must subclass ``BaseExchange`` and implement the
abstract methods for order management and balance retrieval.  Ascent loads
the exchange class at runtime using the ``implementation_class`` field stored
on the Exchange database record, passing the record's ``config`` JSONB to
the constructor.

Example
-------
::

    from ascent.exchanges import BaseExchange, OrderRequest, OrderResponse

    class MyExchange(BaseExchange):
        def submit_order(self, request: OrderRequest) -> OrderResponse:
            # Call exchange API...
            return OrderResponse(
                exchange_order_id="abc123",
                status="SUBMITTED",
            )

        def cancel_order(self, exchange_order_id: str) -> OrderResponse:
            ...

        def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
            ...

        def get_balances(self) -> list[BalanceEntry]:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class OrderRequest(BaseModel):
    """Data submitted to an exchange for order execution."""

    order_type: str
    side: str
    from_asset_symbol: str
    to_asset_symbol: str
    quantity: float
    price: float | None = None
    time_in_force: str | None = None
    client_order_id: str | None = None


class OrderResponse(BaseModel):
    """Response returned from an exchange after order submission or cancellation."""

    exchange_order_id: str
    status: str
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    error_message: str | None = None


class OrderStatusResponse(BaseModel):
    """Response returned when polling order status."""

    exchange_order_id: str
    status: str
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    error_message: str | None = None


class BalanceEntry(BaseModel):
    """A single asset balance on the exchange."""

    asset_symbol: str
    available: float
    reserved: float = 0.0
    total: float


class BaseExchange(ABC):
    """Abstract base class that every Ascent exchange integration must inherit from.

    The ``config`` dict is populated from the Exchange database record's JSONB
    ``config`` column, allowing each exchange instance to be configured
    independently (API keys, endpoints, rate limits, etc.).
    """

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResponse:
        """Submit an order for execution on the exchange."""

    @abstractmethod
    def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        """Cancel an existing order by its exchange-assigned ID."""

    @abstractmethod
    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        """Poll the current status of an order."""

    @abstractmethod
    def get_balances(self) -> list[BalanceEntry]:
        """Return current account balances on the exchange."""

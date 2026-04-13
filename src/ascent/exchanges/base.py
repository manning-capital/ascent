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

import re
from abc import ABC, abstractmethod
from typing import ClassVar

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

    Subclasses declare class-level attributes for auto-registration::

        class KrakenSpot(BaseExchange):
            provider = "KRAKEN"
            instrument_type = "SECURITY"
            display_name = "Kraken Spot"

            def submit_order(self, request):
                ...
    """

    #: Provider name or UUID.  Resolved at deploy time.
    provider: ClassVar[str | None] = None

    #: Instrument type name or UUID.  Resolved at deploy time.
    instrument_type: ClassVar[str | None] = None

    #: Human-readable name shown in the UI.  Auto-derived from class name if not set.
    display_name: ClassVar[str | None] = None

    #: Optional description.
    description: ClassVar[str | None] = None

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

    # ------------------------------------------------------------------
    # Name / ref helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_name(cls) -> str:
        """Return the unique name (``UPPER_SNAKE_CASE``)."""
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", cls.__name__).upper()

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name, auto-derived from the class name if not set."""
        if cls.display_name:
            return cls.display_name
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cls.__name__)

    @classmethod
    def ref(cls) -> str:
        """Canonical reference for DB lookup."""
        return cls.get_name()

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    @classmethod
    def run(
        cls,
        *,
        database_url: str | None = None,
        redis_url: str | None = None,
        log_level: str = "INFO",
    ) -> None:
        """Deploy and run this exchange as a long-running process.

        Registers (or updates) the exchange in the database, then starts
        a Redis pub/sub listener that accepts order requests from strategies
        and dispatches them to the exchange implementation.
        """
        from ascent.engine.runner import Runner

        runner = Runner(
            database_url=database_url,
            redis_url=redis_url,
            log_level=log_level,
        )
        runner.add(cls)
        runner.run()

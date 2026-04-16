"""ExchangePort — async wrapper around user-supplied ``BaseExchange`` implementations.

User exchange classes are synchronous by design (they call third-party SDKs).
The adapter runs them on a threadpool so they don't block the asyncio loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ascent.exchanges.base import (
    BalanceEntry,
    OrderEvent,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)


@runtime_checkable
class ExchangePort(Protocol):
    """Adapter-side view of a single exchange implementation."""

    poll_interval: float
    supports_streaming: bool
    supports_polling: bool

    async def submit_order(self, request: OrderRequest) -> OrderResponse: ...

    async def cancel_order(self, exchange_order_id: str) -> OrderResponse: ...

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse: ...

    async def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None: ...

    async def get_balances(self) -> list[BalanceEntry]: ...

    async def get_open_orders(self) -> list[OrderStatusResponse]: ...

    def stream_orders(self) -> AsyncIterator[OrderEvent]: ...

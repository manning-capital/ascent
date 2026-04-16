"""ExchangeAdapter — wraps a user-supplied :class:`BaseExchange` as an ExchangePort.

User exchanges are synchronous by design (they call third-party SDKs). The
adapter uses ``asyncio.to_thread`` for every call so the event loop stays free.
Streaming is bridged via an ``asyncio.Queue`` drained by a thread worker.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator

from ascent.exchanges.base import (
    BalanceEntry,
    BaseExchange,
    OrderEvent,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)
from ascent.ports import ExchangePort


class ExchangeAdapter(ExchangePort):
    def __init__(self, exchange: BaseExchange) -> None:
        self._ex = exchange
        self.poll_interval = exchange.poll_interval
        self.supports_streaming = (
            type(exchange).connect_order_stream is not BaseExchange.connect_order_stream
        )
        self.supports_polling = type(exchange).get_open_orders is not BaseExchange.get_open_orders

    async def submit_order(self, request: OrderRequest) -> OrderResponse:
        return await asyncio.to_thread(self._ex.submit_order, request)

    async def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        return await asyncio.to_thread(self._ex.cancel_order, exchange_order_id)

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        return await asyncio.to_thread(self._ex.get_order_status, exchange_order_id)

    async def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None:
        try:
            return await asyncio.to_thread(self._ex.get_order_by_client_id, client_order_id)
        except NotImplementedError:
            return None

    async def get_balances(self) -> list[BalanceEntry]:
        return await asyncio.to_thread(self._ex.get_balances)

    async def get_open_orders(self) -> list[OrderStatusResponse]:
        if not self.supports_polling:
            return []
        return await asyncio.to_thread(self._ex.get_open_orders)

    async def stream_orders(self) -> AsyncIterator[OrderEvent]:
        if not self.supports_streaming:
            return
        queue: asyncio.Queue[OrderEvent | None] = asyncio.Queue()
        shutdown = threading.Event()
        loop = asyncio.get_running_loop()

        def worker() -> None:
            try:
                for event in self._ex.connect_order_stream(shutdown):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            shutdown.set()

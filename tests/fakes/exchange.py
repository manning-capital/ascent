"""FakeExchange — scriptable responses for submit/cancel/status; emits events on demand."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ascent.exchanges.base import (
    BalanceEntry,
    OrderEvent,
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
)
from ascent.ports import ExchangePort


@dataclass
class FakeExchange(ExchangePort):
    poll_interval: float = 0.1
    supports_streaming: bool = False
    supports_polling: bool = True

    submissions: list[OrderRequest] = field(default_factory=list)
    next_response: OrderResponse | None = None
    open_orders: list[OrderStatusResponse] = field(default_factory=list)
    by_client_id: dict[str, OrderStatusResponse] = field(default_factory=dict)
    balances: list[BalanceEntry] = field(default_factory=list)

    _stream: asyncio.Queue[OrderEvent] = field(default_factory=asyncio.Queue)

    async def submit_order(self, request: OrderRequest) -> OrderResponse:
        self.submissions.append(request)
        if self.next_response is not None:
            return self.next_response
        return OrderResponse(
            exchange_order_id=f"EX-{uuid.uuid4().hex[:8]}",
            status="SUBMITTED",
        )

    async def cancel_order(self, exchange_order_id: str) -> OrderResponse:
        return OrderResponse(exchange_order_id=exchange_order_id, status="CANCELLED")

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse:
        for status in self.open_orders:
            if status.exchange_order_id == exchange_order_id:
                return status
        return OrderStatusResponse(exchange_order_id=exchange_order_id, status="NOT_FOUND")

    async def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None:
        return self.by_client_id.get(client_order_id)

    async def get_balances(self) -> list[BalanceEntry]:
        return list(self.balances)

    async def get_open_orders(self) -> list[OrderStatusResponse]:
        return list(self.open_orders)

    async def stream_orders(self) -> AsyncIterator[OrderEvent]:
        while True:
            event = await self._stream.get()
            yield event

    def push_stream_event(self, event: OrderEvent) -> None:
        self._stream.put_nowait(event)

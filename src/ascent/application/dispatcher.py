"""DispatcherService — consumes dispatch intents from JetStream and forwards to the exchange.

Replaces the Redis-subscribe dispatch loop that used to live inside
:class:`ExchangeService`. Each :class:`DispatcherService` instance owns one
exchange's dispatch consumer — ``ascent.exchange.<exchange_id>`` on the
JetStream ``ASCENT_EXCHANGE`` stream — and calls ``submit_order`` or
``cancel_order`` on the corresponding :class:`ExchangePort`.

Ack strategy:

- Success → ``ack()``. JetStream advances the cursor.
- Payload is malformed → ``term()``. Never retry; re-delivery won't fix bad JSON.
- Broker raises an unknown exception → ``ack()`` for now, with a log. In
  a later phase the plugin's ``classify_error`` decides nak vs term.

Submit responses are still published on Redis (``{channel}.responses``) so
the phase-4 :class:`FillHandlerService` keeps working. Phase 7 moves the
responses side to JetStream too.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from ascent.exchanges.base import OrderRequest
from ascent.ports import Clock, DurableConsumer, DurablePublisher, ExchangePort

logger = logging.getLogger(__name__)


@dataclass
class DispatcherService:
    exchange_id: uuid.UUID
    exchange: ExchangePort
    consumer: DurableConsumer
    responses_subject: str
    responses_publisher: DurablePublisher
    clock: Clock
    open_orders: dict[str, dict] = field(default_factory=dict)

    async def run_forever(self) -> None:
        logger.info("DispatcherService starting for exchange %s", self.exchange_id)
        try:
            async for msg in self.consumer:
                await self._handle(msg)
        except asyncio.CancelledError:
            logger.info("DispatcherService %s cancelled", self.exchange_id)
            raise
        finally:
            await self.consumer.aclose()

    async def _handle(self, msg) -> None:
        payload = msg.payload
        action = payload.get("action")
        try:
            if action == "submit_order":
                await self._dispatch_submit(payload)
            elif action == "cancel_order":
                await self._dispatch_cancel(payload)
            else:
                logger.warning(
                    "Dispatcher: unknown action '%s' on exchange %s", action, self.exchange_id
                )
                await msg.term()
                return
            await msg.ack()
        except (KeyError, TypeError, ValueError):
            # Malformed payload — never retry. Poison message goes to DLQ.
            logger.exception("Dispatcher: malformed payload, terming message")
            await msg.term()
        except Exception:
            # Unknown broker/platform error. Ack for now to avoid a tight
            # redelivery loop; phase 7 introduces classify_error for proper
            # routing.
            logger.exception("Dispatcher: unhandled exception; acking to prevent redelivery storm")
            await msg.ack()

    async def _dispatch_submit(self, payload: dict) -> None:
        request = OrderRequest(**payload["order"])
        response = await self.exchange.submit_order(request)
        self.open_orders[response.exchange_order_id] = {
            "order_id": payload.get("order_id"),
            "trade_id": payload.get("trade_id"),
            "trade_leg_id": payload.get("trade_leg_id"),
            "last_status": None,
            "last_filled": 0.0,
        }
        await self._publish_response("order_response", payload, response.model_dump())

    async def _dispatch_cancel(self, payload: dict) -> None:
        eid = payload["exchange_order_id"]
        response = await self.exchange.cancel_order(eid)
        meta = self.open_orders.pop(eid, {})
        await self._publish_response("order_update", meta, response.model_dump())

    async def _publish_response(self, action: str, meta: dict, response: dict) -> None:
        # Stable msg_id: same logical event → same id → broker dedups.
        # Covers the "we redelivered the same exchange state" case.
        ex_order_id = response.get("exchange_order_id") or "unknown"
        status = response.get("status") or "unknown"
        filled = response.get("filled_quantity") or 0
        msg_id = f"{self.exchange_id}:{ex_order_id}:{status}:{filled}:{action}"
        await self.responses_publisher.publish(
            self.responses_subject,
            {
                "action": action,
                "exchange_id": str(self.exchange_id),
                "order_id": meta.get("order_id"),
                "trade_id": meta.get("trade_id"),
                "trade_leg_id": meta.get("trade_leg_id"),
                "response": response,
            },
            msg_id=msg_id,
        )

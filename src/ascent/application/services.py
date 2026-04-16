"""Long-running services that glue use cases into asyncio tasks.

Each service owns one concern and runs until cancelled. The Runner
composes these under a single ``asyncio.TaskGroup``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import pandas as pd

from ascent.application.execute_feed import FeedContext, FeedExecutor, FeedFetcher
from ascent.application.persist_feed import FeedPersister
from ascent.application.process_fill import FillProcessor
from ascent.application.reconcile_orders import OrderReconciler
from ascent.domain import FillEvent, OrderState, PartitionWindow
from ascent.exchanges.base import OrderRequest
from ascent.feeds.schedule import Schedule
from ascent.ports import (
    Clock,
    EventBus,
    ExchangePort,
    LatestFeedStore,
    RunTrackerPort,
)

logger = logging.getLogger(__name__)


class FetcherFactory(Protocol):
    def __call__(
        self,
        partition: PartitionWindow | None,
        context: dict[str, Any],
    ) -> FeedFetcher: ...


# ---------------------------------------------------------------------------
# Scheduled feed
# ---------------------------------------------------------------------------


@dataclass
class ScheduledFeedService:
    feed: FeedContext
    executor: FeedExecutor
    run_tracker: RunTrackerPort
    clock: Clock
    fetcher_factory: FetcherFactory

    async def run_forever(self) -> None:
        if self.feed.schedule is None:
            raise ValueError("ScheduledFeedService requires a schedule")
        logger.info("ScheduledFeed %s starting", self.feed.feed_ref)
        try:
            while True:
                tick = await self.clock.sleep_until_tick(self.feed.schedule)
                await self._run_once(tick)
        except asyncio.CancelledError:
            logger.info("ScheduledFeed %s cancelled", self.feed.feed_ref)
            raise

    async def _run_once(self, tick: datetime) -> None:
        logger.info("ScheduledFeed %s tick at %s", self.feed.feed_ref, tick.isoformat())
        async with self.run_tracker.track_feed_run(self.feed.feed_id) as run_id:
            fetcher = self.fetcher_factory(None, {})
            outcome = await self.executor.execute(
                feed=self.feed,
                tick=tick,
                fetcher=fetcher,
                feed_run_id=run_id,
            )
            logger.info(
                "ScheduledFeed %s produced %d rows (run_id=%s)",
                self.feed.feed_ref,
                outcome.rows,
                run_id,
            )


# ---------------------------------------------------------------------------
# Triggered feed
# ---------------------------------------------------------------------------


@dataclass
class TriggeredFeedService:
    feed: FeedContext
    parent_channels: list[str]
    parent_refs: dict[uuid.UUID, str]
    effective_schedule: Schedule | None
    executor: FeedExecutor
    run_tracker: RunTrackerPort
    event_bus: EventBus
    feed_store: LatestFeedStore
    fetcher_factory: FetcherFactory

    async def run_forever(self) -> None:
        logger.info("TriggeredFeed %s starting", self.feed.feed_ref)
        parent_ids = set(self.parent_refs.keys())
        satisfied: set[uuid.UUID] = set()
        latest_partition_key: datetime | None = None

        # Schedule overrides for the executor — parents drive tick cadence.
        executor_feed = (
            FeedContext(
                feed_id=self.feed.feed_id,
                feed_ref=self.feed.feed_ref,
                channel=self.feed.channel,
                output_table=self.feed.output_table,
                schedule=self.effective_schedule,
            )
            if self.effective_schedule
            else self.feed
        )

        sub = self.event_bus.subscribe(self.parent_channels)
        try:
            async for event in sub:
                parent_id = uuid.UUID(event.payload["feed_id"])
                if parent_id not in parent_ids:
                    continue
                satisfied.add(parent_id)
                pk_raw = event.payload.get("partition_key")
                if pk_raw:
                    latest_partition_key = datetime.fromisoformat(pk_raw)

                if not parent_ids.issubset(satisfied):
                    continue

                await self._fire(executor_feed, latest_partition_key)
                satisfied.clear()
        except asyncio.CancelledError:
            logger.info("TriggeredFeed %s cancelled", self.feed.feed_ref)
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()

    async def _fire(self, executor_feed: FeedContext, partition_key: datetime | None) -> None:
        async with self.run_tracker.track_feed_run(self.feed.feed_id) as run_id:
            # Load parent data snapshots so the fetcher can use get_feed().
            parent_data = await self.feed_store.get_latest_many(list(self.parent_refs.keys()))
            context = {
                self.parent_refs[pid]: df for pid, df in parent_data.items() if df is not None
            }
            tick = partition_key or datetime.now(tz=UTC)
            fetcher = self.fetcher_factory(None, context)
            await self.executor.execute(
                feed=executor_feed,
                tick=tick,
                fetcher=fetcher,
                feed_run_id=run_id,
                extra_context=context,
            )


# ---------------------------------------------------------------------------
# Exchange dispatcher + monitor
# ---------------------------------------------------------------------------


@dataclass
class ExchangeService:
    exchange_id: uuid.UUID
    exchange: ExchangePort
    channel: str
    event_bus: EventBus
    reconciler: OrderReconciler
    clock: Clock
    open_orders: dict[str, dict] = field(default_factory=dict)

    async def run_forever(self) -> None:
        await self.reconciler.reconcile(
            exchange=self.exchange,
            exchange_id=self.exchange_id,
            now=self.clock.now(),
        )

        tasks = [asyncio.create_task(self._dispatch_loop())]
        if self.exchange.supports_streaming:
            tasks.append(asyncio.create_task(self._stream_loop()))
        elif self.exchange.supports_polling:
            tasks.append(asyncio.create_task(self._poll_loop()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise

    async def _dispatch_loop(self) -> None:
        sub = self.event_bus.subscribe([self.channel])
        try:
            async for event in sub:
                await self._dispatch(event.payload)
        except asyncio.CancelledError:
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()

    async def _dispatch(self, payload: dict) -> None:
        action = payload.get("action")
        try:
            if action == "submit_order":
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
            elif action == "cancel_order":
                eid = payload["exchange_order_id"]
                response = await self.exchange.cancel_order(eid)
                meta = self.open_orders.pop(eid, {})
                await self._publish_response("order_update", meta, response.model_dump())
            else:
                logger.warning("Unknown action '%s' on exchange %s", action, self.exchange_id)
        except Exception:
            logger.exception("Exchange dispatch error on %s", action)

    async def _poll_loop(self) -> None:
        while True:
            if not self.open_orders:
                await asyncio.sleep(self.exchange.poll_interval)
                continue
            try:
                statuses = await self.exchange.get_open_orders()
            except Exception:
                logger.exception("poll error")
                await asyncio.sleep(self.exchange.poll_interval)
                continue
            for status in statuses:
                meta = self.open_orders.get(status.exchange_order_id)
                if meta is None:
                    continue
                if (
                    status.status == meta["last_status"]
                    and status.filled_quantity == meta["last_filled"]
                ):
                    continue
                meta["last_status"] = status.status
                meta["last_filled"] = status.filled_quantity
                await self._publish_response("order_update", meta, status.model_dump())
                if status.status in ("FILLED", "CANCELLED", "REJECTED"):
                    self.open_orders.pop(status.exchange_order_id, None)
            await asyncio.sleep(self.exchange.poll_interval)

    async def _stream_loop(self) -> None:
        async for event in self.exchange.stream_orders():
            meta = self.open_orders.get(event.exchange_order_id)
            if meta is None:
                continue
            payload = {
                "exchange_order_id": event.exchange_order_id,
                "status": event.status,
                "filled_quantity": event.filled_quantity,
                "average_fill_price": event.average_fill_price,
            }
            await self._publish_response("order_update", meta, payload)
            if event.status in ("FILLED", "CANCELLED", "REJECTED"):
                self.open_orders.pop(event.exchange_order_id, None)

    async def _publish_response(self, action: str, meta: dict, response: dict) -> None:
        await self.event_bus.publish(
            f"{self.channel}.responses",
            {
                "action": action,
                "exchange_id": str(self.exchange_id),
                "order_id": meta.get("order_id"),
                "trade_id": meta.get("trade_id"),
                "trade_leg_id": meta.get("trade_leg_id"),
                "response": response,
            },
        )


# ---------------------------------------------------------------------------
# Fill handler
# ---------------------------------------------------------------------------


@dataclass
class FillHandlerService:
    response_channels: list[str]
    event_bus: EventBus
    processor: FillProcessor
    clock: Clock

    async def run_forever(self) -> None:
        logger.info("FillHandler subscribing to %d channel(s)", len(self.response_channels))
        sub = self.event_bus.subscribe(self.response_channels)
        try:
            async for event in sub:
                payload = event.payload
                if payload.get("action") != "order_update":
                    continue
                trade_id = payload.get("trade_id")
                order_id = payload.get("order_id")
                response = payload.get("response", {})
                status = response.get("status")
                if not (trade_id and order_id and status):
                    continue
                try:
                    state = OrderState(status)
                except ValueError:
                    logger.warning("Fill handler: unknown status '%s'", status)
                    continue
                fill = FillEvent(
                    order_id=uuid.UUID(order_id),
                    state=state,
                    filled_quantity=response.get("filled_quantity") or 0.0,
                    average_fill_price=response.get("average_fill_price"),
                    external_order_id=response.get("exchange_order_id"),
                    error_message=response.get("error_message"),
                )
                try:
                    await self.processor.process(
                        trade_id=uuid.UUID(trade_id),
                        event=fill,
                        now=self.clock.now(),
                    )
                except Exception:
                    logger.exception("FillProcessor error")
        except asyncio.CancelledError:
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@dataclass
class PersistenceService:
    feed_channels: list[str]
    feed_id_to_output: dict[uuid.UUID, str]
    event_bus: EventBus
    persister: FeedPersister

    async def run_forever(self) -> None:
        sub = self.event_bus.subscribe(self.feed_channels)
        try:
            async for event in sub:
                feed_id = uuid.UUID(event.payload["feed_id"])
                output_table = self.feed_id_to_output.get(feed_id) or event.payload.get("schema")
                if output_table is None:
                    continue
                try:
                    await self.persister.persist(feed_id=feed_id, output_table=output_table)
                except Exception:
                    logger.exception("PersistService error for feed %s", feed_id)
        except asyncio.CancelledError:
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()


# keep a reference so pd import isn't dropped — used only in type hints above
_ = pd

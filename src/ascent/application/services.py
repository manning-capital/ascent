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
from ascent.domain import Context, ContextSource, FillEvent, OrderState
from ascent.feeds.schedule import Schedule
from ascent.ports import (
    Clock,
    DurableConsumer,
    DurablePublisher,
    EventBus,
    ExchangePort,
    LatestFeedStore,
    RunTrackerPort,
)

logger = logging.getLogger(__name__)


_OUTPUT_TABLE_TO_SCOPE = {
    "instrument_attribute": "instrument",
    "instrument_period_attribute": "instrument",
    "composite_attribute": "composite",
    "composite_period_attribute": "composite",
}


def _build_feed_run_context(feed: FeedContext, snapshot_timestamp: datetime) -> Context:
    """Build the persisted ``Context`` for a feed-run row.

    Captures what we know at run-start without actually invoking the feed:
    the target table, the scope type derived from the table name, and the
    snapshot timestamp. ``attributes`` is left empty for now — the chart
    API discovers them at query time by joining the attribute table.
    """
    scope_type = _OUTPUT_TABLE_TO_SCOPE.get(feed.output_table)
    if scope_type is None:
        # Unknown output table — skip context capture; the persister will
        # likely fail downstream, but we don't want to block run creation.
        return Context(snapshot_timestamp=snapshot_timestamp, sources=[])
    return Context(
        snapshot_timestamp=snapshot_timestamp,
        sources=[
            ContextSource(
                table=feed.output_table,  # type: ignore[arg-type]
                scope_type=scope_type,  # type: ignore[arg-type]
                attributes=[],
            )
        ],
    )


class FetcherFactory(Protocol):
    def __call__(
        self,
        snapshot_timestamp: datetime,
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
        snapshot = self.executor.resolve_snapshot(self.feed, tick)
        logger.info(
            "ScheduledFeed %s tick at %s snapshot=%s",
            self.feed.feed_ref,
            tick.isoformat(),
            snapshot.isoformat(),
        )
        async with self.run_tracker.track_feed_run(
            self.feed.feed_id,
            snapshot_timestamp=snapshot,
            context=_build_feed_run_context(self.feed, snapshot),
        ) as run_id:
            fetcher = self.fetcher_factory(snapshot, {})
            outcome = await self.executor.execute(
                feed=self.feed,
                tick=tick,
                snapshot_timestamp=snapshot,
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
        latest_snapshot: datetime | None = None
        latest_parent_run_ids: dict[uuid.UUID, uuid.UUID] = {}

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
                ts_raw = event.payload.get("snapshot_timestamp")
                if ts_raw:
                    latest_snapshot = datetime.fromisoformat(ts_raw)
                run_id_raw = event.payload.get("feed_run_id")
                if run_id_raw:
                    latest_parent_run_ids[parent_id] = uuid.UUID(run_id_raw)

                if not parent_ids.issubset(satisfied):
                    continue

                await self._fire(executor_feed, latest_snapshot)
                satisfied.clear()
        except asyncio.CancelledError:
            logger.info("TriggeredFeed %s cancelled", self.feed.feed_ref)
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()

    async def _fire(self, executor_feed: FeedContext, parent_snapshot: datetime | None) -> None:
        # Triggered feeds inherit the parent's snapshot. If the parent didn't
        # carry one (shouldn't happen once scheduled feeds always publish it),
        # fall back to wall-clock — the executor will resolve it against the
        # effective schedule if one is set.
        tick = parent_snapshot or datetime.now(tz=UTC)
        snapshot = self.executor.resolve_snapshot(executor_feed, tick)
        async with self.run_tracker.track_feed_run(
            self.feed.feed_id,
            snapshot_timestamp=snapshot,
            context=_build_feed_run_context(self.feed, snapshot),
        ) as run_id:
            # Load parent data snapshots so the fetcher can use get_feed().
            parent_data = await self.feed_store.get_latest_many(list(self.parent_refs.keys()))
            context = {
                self.parent_refs[pid]: df for pid, df in parent_data.items() if df is not None
            }
            fetcher = self.fetcher_factory(snapshot, context)
            await self.executor.execute(
                feed=executor_feed,
                tick=tick,
                snapshot_timestamp=snapshot,
                fetcher=fetcher,
                feed_run_id=run_id,
                extra_context=context,
            )


# ---------------------------------------------------------------------------
# Exchange dispatcher + monitor
# ---------------------------------------------------------------------------


@dataclass
class ExchangeService:
    """Monitors exchange-side fills and publishes them durably on JetStream.

    The dispatch (submit/cancel) path was moved to :class:`DispatcherService`
    as part of phase 6 — that consumer reads from JetStream and owns the
    ``open_orders`` map. This service now only runs the reconciler at
    startup and then streams/polls the exchange for fill updates.

    Responses publish to ``responses_subject`` via the :class:`DurablePublisher`.
    FillHandlerService consumes from the same subject through a JetStream
    durable consumer (phase 7).

    ``open_orders`` here is a secondary copy used by the poll/stream loops
    so we know which exchange_order_ids to track. It's populated by the
    DispatcherService on submit and read here on poll/stream.
    """

    exchange_id: uuid.UUID
    exchange: ExchangePort
    responses_subject: str
    responses_publisher: DurablePublisher
    reconciler: OrderReconciler
    clock: Clock
    open_orders: dict[str, dict] = field(default_factory=dict)

    async def run_forever(self) -> None:
        await self.reconciler.reconcile(
            exchange=self.exchange,
            exchange_id=self.exchange_id,
            now=self.clock.now(),
        )

        tasks: list[asyncio.Task] = []
        if self.exchange.supports_streaming:
            tasks.append(asyncio.create_task(self._stream_loop()))
        elif self.exchange.supports_polling:
            tasks.append(asyncio.create_task(self._poll_loop()))
        if not tasks:
            return  # nothing to monitor for this exchange

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise

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


# ---------------------------------------------------------------------------
# Fill handler
# ---------------------------------------------------------------------------


@dataclass
class FillHandlerService:
    """Consumes order-update responses from JetStream and feeds them to the
    :class:`FillProcessor`.

    Ack strategy:
    - successful process → ``ack()``
    - unparseable payload (bad trade_id / unknown status) → ``ack()`` after
      logging. Retrying won't fix garbage.
    - FillProcessor raises unexpectedly → ``nak()`` so the broker
      redelivers after ack-wait. Transient DB errors benefit from retry.
    """

    consumer: DurableConsumer
    processor: FillProcessor
    clock: Clock

    async def run_forever(self) -> None:
        logger.info("FillHandler starting")
        try:
            async for msg in self.consumer:
                await self._handle(msg)
        except asyncio.CancelledError:
            logger.info("FillHandler cancelled")
            raise
        finally:
            await self.consumer.aclose()

    async def _handle(self, msg) -> None:
        payload = msg.payload
        if payload.get("action") != "order_update":
            await msg.ack()
            return
        trade_id = payload.get("trade_id")
        order_id = payload.get("order_id")
        response = payload.get("response", {})
        status = response.get("status")
        if not (trade_id and order_id and status):
            await msg.ack()
            return
        try:
            state = OrderState(status)
        except ValueError:
            logger.warning("Fill handler: unknown status '%s'", status)
            await msg.ack()
            return
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
            logger.exception("FillProcessor error — naking for redelivery")
            await msg.nak()
            return
        await msg.ack()


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
                ts = self._event_timestamp(event.payload)
                if ts is None:
                    logger.warning(
                        "PersistService: skipping feed %s, event has no snapshot_timestamp",
                        feed_id,
                    )
                    continue
                try:
                    await self.persister.persist(
                        feed_id=feed_id,
                        output_table=output_table,
                        timestamp=ts,
                    )
                except Exception:
                    logger.exception("PersistService error for feed %s", feed_id)
        except asyncio.CancelledError:
            raise
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose:
                await aclose()

    @staticmethod
    def _event_timestamp(payload: dict) -> datetime | None:
        raw = payload.get("snapshot_timestamp")
        if not raw:
            return None
        return datetime.fromisoformat(raw)


# keep a reference so pd import isn't dropped — used only in type hints above
_ = pd

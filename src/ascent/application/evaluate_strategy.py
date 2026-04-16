"""StrategyEvaluator — subscribes to feed channels and evaluates a strategy.

Replaces ``ascent.engine.consumer.run_strategy``. Consumes the event bus,
rebuilds the context DataFrame via :mod:`ascent.application.context_builder`,
and invokes ``strategy.evaluate(ctx)``.

The actual strategy class call is delegated back to the caller — the
evaluator never imports user code directly.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ascent.application.context_builder import FeedFrame, Scope, build_context
from ascent.application.trigger import StrategyFeedSpec, should_evaluate
from ascent.ports import Clock, EventBus, LatestFeedStore, RunTrackerPort, TradeRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedBinding:
    spec: StrategyFeedSpec
    feed_ref: str
    channel: str
    is_composite_scoped: bool


Evaluator = Callable[[pd.DataFrame, uuid.UUID], Awaitable[None]]
"""User callback: given a context DataFrame and a strategy_run_id, evaluate the strategy."""


class StrategyEvaluator:
    def __init__(
        self,
        *,
        strategy_id: uuid.UUID,
        feeds: list[FeedBinding],
        scope: Scope,
        composite_members: dict[uuid.UUID, list[uuid.UUID]] | None,
        trade_repo: TradeRepository,
        feed_store: LatestFeedStore,
        event_bus: EventBus,
        run_tracker: RunTrackerPort,
        clock: Clock,
        evaluator: Evaluator,
        attribute_map: dict[uuid.UUID, str] | None = None,
    ) -> None:
        self._strategy_id = strategy_id
        self._feeds = feeds
        self._scope: Scope = scope
        self._composite_members = composite_members or {}
        self._trades = trade_repo
        self._store = feed_store
        self._bus = event_bus
        self._tracker = run_tracker
        self._clock = clock
        self._evaluate = evaluator
        # Look up attribute UUIDs (which arrive as strings through Redis JSON)
        # to the attribute names the strategy's context DataFrame uses.
        self._attribute_name_by_str: dict[str, str] = (
            {str(k): v for k, v in attribute_map.items()} if attribute_map else {}
        )

    async def run_forever(self) -> None:
        feed_channels = [b.channel for b in self._feeds]
        satisfied: set[uuid.UUID] = set()
        latest_run_ids: dict[uuid.UUID, uuid.UUID] = {}

        await self._warm_cache(satisfied)

        subscription = self._bus.subscribe(feed_channels)
        try:
            async for event in subscription:
                await self._handle_event(event, satisfied, latest_run_ids)
        except asyncio.CancelledError:
            logger.info("StrategyEvaluator %s cancelled", self._strategy_id)
            raise
        finally:
            aclose = getattr(subscription, "aclose", None)
            if aclose:
                await aclose()

    async def _warm_cache(self, satisfied: set[uuid.UUID]) -> None:
        data = await self._store.get_latest_many([b.spec.feed_id for b in self._feeds])
        for fid, df in data.items():
            if df is not None and not df.empty:
                satisfied.add(fid)

    async def _handle_event(
        self,
        event,
        satisfied: set[uuid.UUID],
        latest_run_ids: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        payload = event.payload
        updated_feed_id = uuid.UUID(payload["feed_id"])
        run_id_raw = payload.get("feed_run_id")
        if run_id_raw:
            latest_run_ids[updated_feed_id] = uuid.UUID(run_id_raw)
        satisfied.add(updated_feed_id)

        if not should_evaluate(
            updated_feed_id=updated_feed_id,
            strategy_feeds=[b.spec for b in self._feeds],
            satisfied_feed_ids=satisfied,
        ):
            return

        async with self._tracker.track_strategy_run(self._strategy_id) as run_id:
            ctx = await self._build_context()
            await self._evaluate(ctx, run_id)

    async def _build_context(self) -> pd.DataFrame:
        latest = await self._store.get_latest_many([b.spec.feed_id for b in self._feeds])
        frames: list[FeedFrame] = []
        for binding in self._feeds:
            df = latest.get(binding.spec.feed_id)
            if df is None or df.empty:
                continue
            frames.append(
                FeedFrame(
                    feed_id=binding.spec.feed_id,
                    feed_name=binding.feed_ref.lower(),
                    is_composite_scoped=binding.is_composite_scoped,
                    data=self._resolve_attribute_names(df),
                )
            )
        trades = await self._trades.list_non_terminal_for_strategy(self._strategy_id)
        return build_context(
            scope=self._scope,
            feed_frames=frames,
            trades=trades,
            composite_members=self._composite_members,
        )

    def _resolve_attribute_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add an ``attribute_name`` column derived from ``attribute_id``.

        Redis → JSON round-trips convert UUIDs to strings, so we match on
        strings and fall back to the raw id for unknown attributes.
        """
        if "attribute_id" not in df.columns:
            return df
        out = df.copy()
        ids_as_str = out["attribute_id"].astype(str)
        out["attribute_name"] = ids_as_str.map(self._attribute_name_by_str).fillna(ids_as_str)
        return out


_ = datetime  # silence unused-import from re-exports

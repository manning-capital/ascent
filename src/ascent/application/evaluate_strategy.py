"""StrategyEvaluator — subscribes to feed channels and evaluates a strategy.

Replaces ``ascent.engine.consumer.run_strategy``. Consumes the event bus,
rebuilds the :class:`Context` via :mod:`ascent.application.context_builder`,
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

from ascent.application.context_builder import Context, FeedFrame, Scope, build_context
from ascent.application.trigger import StrategyFeedSpec, should_evaluate
from ascent.ports import (
    Clock,
    EventBus,
    LatestFeedStore,
    RunTrackerPort,
    StrategyUniverseRepository,
    TradeRepository,
    UnitOfWorkFactory,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedBinding:
    spec: StrategyFeedSpec
    feed_ref: str
    channel: str
    is_composite_scoped: bool


Evaluator = Callable[[Context, uuid.UUID], Awaitable[None]]
"""User callback: given a :class:`Context` and a strategy_run_id, evaluate the strategy."""


class StrategyEvaluator:
    def __init__(
        self,
        *,
        strategy_id: uuid.UUID,
        feeds: list[FeedBinding],
        scope: Scope,
        composite_members: dict[uuid.UUID, list[uuid.UUID]] | None,
        trade_repo: TradeRepository,
        universe_repo: StrategyUniverseRepository,
        feed_store: LatestFeedStore,
        event_bus: EventBus,
        run_tracker: RunTrackerPort,
        clock: Clock,
        evaluator: Evaluator,
        uow_factory: UnitOfWorkFactory,
    ) -> None:
        self._strategy_id = strategy_id
        self._feeds = feeds
        self._scope: Scope = scope
        self._composite_members = composite_members or {}
        self._trades = trade_repo
        self._universe_repo = universe_repo
        self._store = feed_store
        self._bus = event_bus
        self._tracker = run_tracker
        self._clock = clock
        self._evaluate = evaluator
        self._uow_factory = uow_factory

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

    async def _build_context(self) -> Context:
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
                    data=df,
                )
            )
        async with self._uow_factory() as uow:
            trades = await self._trades.list_non_terminal_for_strategy(
                uow.session, self._strategy_id
            )
            universe_ids = await self._universe_repo.get_active_universe(
                uow.session, self._strategy_id, self._scope
            )

        open_position_ids = self._derive_open_position_ids(trades)

        return build_context(
            scope=self._scope,
            feed_frames=frames,
            trades=trades,
            composite_members=self._composite_members,
            universe_ids=universe_ids,
            open_position_ids=open_position_ids,
        )

    def _derive_open_position_ids(self, trades) -> set[uuid.UUID]:
        """Map non-terminal trades to scope-appropriate IDs.

        For instrument scope: the union of leg.instrument_id across all
        non-terminal trades. For composite scope: the composite IDs whose
        member-set matches a trade's leg-instrument set (mirrors the
        reverse-lookup that ``_build_trade_columns`` does).
        """
        if self._scope == "instrument":
            return {
                leg.instrument_id
                for trade in trades
                if not trade.state.is_terminal
                for leg in trade.legs
            }

        comp_reverse: dict[frozenset[uuid.UUID], uuid.UUID] = {
            frozenset(members): comp_id for comp_id, members in self._composite_members.items()
        }
        result: set[uuid.UUID] = set()
        for trade in trades:
            if trade.state.is_terminal:
                continue
            leg_ids = frozenset(leg.instrument_id for leg in trade.legs)
            comp_id = comp_reverse.get(leg_ids)
            if comp_id is not None:
                result.add(comp_id)
        return result

_ = datetime  # silence unused-import from re-exports
_ = pd  # keep the pandas import for backwards-compat type hints

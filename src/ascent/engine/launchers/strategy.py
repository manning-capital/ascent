"""Launches one ``StrategyEvaluator`` per strategy under a TaskGroup."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

from ascent.application import FeedBinding, StrategyEvaluator, StrategyFeedSpec
from ascent.application.route_trade import ExchangeBinding, TradeRouter
from ascent.engine.bridges import _SyncRouterProxy
from ascent.engine.context import _current_logger

if TYPE_CHECKING:
    from ascent.engine.contexts import (
        MessagingContext,
        PersistenceContext,
        RuntimeContext,
    )
    from ascent.strategies.base import Strategy

logger = logging.getLogger(__name__)


class StrategyLauncher:
    def __init__(
        self,
        *,
        persistence: PersistenceContext,
        messaging: MessagingContext,
        runtime: RuntimeContext,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._persistence = persistence
        self._messaging = messaging
        self._runtime = runtime
        self._loop = loop

    def launch(self, tg: asyncio.TaskGroup, strategy_cls: type[Strategy]) -> None:
        sid = self._runtime.deployment.strategy_ids[strategy_cls.ref()]
        strategy_info = self._runtime.strategy_info_by_id[sid]

        scope = strategy_cls.scope
        self._validate_feed_scopes(strategy_cls, strategy_info.feed_specs, scope)

        feeds: list[FeedBinding] = []
        for spec in strategy_info.feed_specs:
            feeds.append(
                FeedBinding(
                    spec=StrategyFeedSpec(
                        feed_id=spec.feed_id,
                        is_required=spec.is_required,
                    ),
                    feed_ref=spec.feed_ref,
                    channel=spec.channel,
                    is_composite_scoped=spec.is_composite_scoped,
                )
            )

        composite_members: dict[uuid.UUID, list[uuid.UUID]] = (
            self._runtime.composite_members if scope == "composite" else {}
        )

        strategy_instance = strategy_cls(strategy_info.parameters)
        router = self._build_router(sid, strategy_info)
        if router is not None:
            strategy_instance._trade_router = _SyncRouterProxy(router, self._loop)

        async def evaluator(ctx, run_id: uuid.UUID) -> None:
            if router is not None:
                router.bind_strategy_run(run_id)
            token = _current_logger.set(logger)
            try:
                await asyncio.to_thread(strategy_instance.evaluate, ctx)
            finally:
                _current_logger.reset(token)

        service = StrategyEvaluator(
            strategy_id=sid,
            feeds=feeds,
            scope=scope,
            composite_members=composite_members,
            trade_repo=self._persistence.trade_repo,
            universe_repo=self._persistence.universe_repo,
            feed_store=self._messaging.feed_cache,
            event_bus=self._messaging.event_bus,
            run_tracker=self._persistence.run_tracker,
            strategy_run_repo=self._persistence.strategy_run_repo,
            clock=self._runtime.clock,
            evaluator=evaluator,
            uow_factory=self._persistence.uow_factory,
        )
        tg.create_task(service.run_forever(), name=f"strategy-{strategy_cls.__name__}")

    @staticmethod
    def _validate_feed_scopes(
        strategy_cls: type[Strategy],
        feed_specs,
        scope: str,
    ) -> None:
        """Reject strategies whose declared scope is incompatible with their feeds.

        Instrument-scoped strategies cannot consume composite-scoped feeds —
        there's no well-defined way to align composite rows onto an
        instrument-indexed context. Composite-scoped strategies may consume
        either kind; instrument rows get reindexed onto composite members.
        """
        if scope == "instrument":
            offenders = [spec.feed_ref for spec in feed_specs if spec.is_composite_scoped]
            if offenders:
                raise ValueError(
                    f"Strategy {strategy_cls.__name__!r} declares scope='instrument' "
                    f"but depends on composite-scoped feeds: {offenders}. "
                    f"Either set scope='composite' on the strategy or remove these feeds."
                )

    def _build_router(self, strategy_id: uuid.UUID, info) -> TradeRouter | None:
        if not info.exchanges:
            return None
        return TradeRouter(
            strategy_id=strategy_id,
            trade_repo=self._persistence.trade_repo,
            order_repo=self._persistence.order_repo,
            event_bus=self._messaging.event_bus,
            outbox=self._persistence.outbox_publisher,
            uow_factory=self._persistence.uow_factory,
            exchanges=[
                ExchangeBinding(exchange_id=eid, channel=f"ascent.exchange.{eid}")
                for eid in info.exchanges
            ],
            route_gate=self._persistence.route_gate,
            instrument_repo=self._persistence.instrument_repo,
        )

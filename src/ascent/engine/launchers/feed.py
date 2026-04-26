"""Launches per-feed services (scheduled or triggered) under a TaskGroup."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ascent.application import (
    FeedContext,
    ScheduledFeedService,
    TriggeredFeedService,
)
from ascent.engine.bridges import _fetcher_factory
from ascent.feeds.schedule import Schedule

if TYPE_CHECKING:
    from ascent.engine.contexts import (
        MessagingContext,
        PersistenceContext,
        RuntimeContext,
    )
    from ascent.feeds.base import Feed

logger = logging.getLogger(__name__)


class FeedLauncher:
    def __init__(
        self,
        *,
        persistence: PersistenceContext,
        messaging: MessagingContext,
        runtime: RuntimeContext,
    ) -> None:
        self._persistence = persistence
        self._messaging = messaging
        self._runtime = runtime

    def launch(self, tg: asyncio.TaskGroup, feed_cls: type[Feed]) -> None:
        """Start the correct feed service for ``feed_cls``; no-op for external feeds."""
        record = self._runtime.feed_records[self._runtime.deployment.feed_ids[feed_cls.ref()]]

        if feed_cls.is_streaming():
            logger.warning("Streaming feed %s not yet supported, skipping", feed_cls.ref())
            return

        feed_model = record.model
        feed_ctx = FeedContext(
            feed_id=feed_model.id,
            feed_ref=feed_model.feed_ref,
            channel=feed_model.channel,
            output_table=feed_model.output_table,
            schedule=Schedule(**feed_model.schedule) if feed_model.schedule else None,
        )
        factory = _fetcher_factory(
            feed_cls,
            feed_model.parameters or {},
            feed_id=feed_model.id,
            is_composite_scoped=record.is_composite_scoped,
            session_factory=self._persistence.session_factory,
        )

        if feed_cls.schedule is not None:
            service = ScheduledFeedService(
                feed=feed_ctx,
                executor=self._runtime.executor,
                run_tracker=self._persistence.run_tracker,
                clock=self._runtime.clock,
                fetcher_factory=factory,
            )
            tg.create_task(service.run_forever(), name=f"feed-{feed_cls.__name__}")
            return

        if feed_cls.depends_on:
            parent_channels = [p.channel for p in record.parent_records.values() if p]
            parent_refs = {p.id: p.feed_ref for p in record.parent_records.values() if p}
            parent_schedules = [
                Schedule(**p.schedule) for p in record.parent_records.values() if p and p.schedule
            ]
            effective = min(parent_schedules, key=lambda s: s.interval, default=None)
            service = TriggeredFeedService(
                feed=feed_ctx,
                parent_channels=parent_channels,
                parent_refs=parent_refs,
                effective_schedule=effective,
                executor=self._runtime.executor,
                run_tracker=self._persistence.run_tracker,
                event_bus=self._messaging.event_bus,
                feed_store=self._messaging.feed_cache,
                fetcher_factory=factory,
            )
            tg.create_task(service.run_forever(), name=f"feed-{feed_cls.__name__}")
            return

        logger.info("Feed %s is external (no schedule or depends_on), skipping", feed_cls.ref())

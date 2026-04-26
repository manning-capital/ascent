"""Launcher for the global, non-per-entity services.

Heartbeat, outbox relay, fill handler, and optional DB-writer persistence are
not per-item, so they don't fit alongside feed/strategy/exchange launchers.
Keeping them here concentrates all TaskGroup scheduling into launchers and
makes the Runner's orchestration a series of uniform ``.launch_*(tg, ...)``
calls.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from ascent.adapters.nats import NatsJetStreamConsumer
from ascent.application import (
    FillHandlerService,
    HeartbeatService,
    PersistenceService,
)
from ascent.application.outbox_relay import OutboxRelay

if TYPE_CHECKING:
    from ascent.engine.contexts import (
        MessagingContext,
        PersistenceContext,
        RuntimeContext,
    )
    from ascent.engine.queries import FeedRecord


class GlobalServicesLauncher:
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

    def launch_heartbeat(
        self,
        tg: asyncio.TaskGroup,
        targets: list[tuple[str, uuid.UUID]],
    ) -> None:
        service = HeartbeatService(
            heartbeat_store=self._messaging.heartbeat_store,
            targets=targets,
        )
        tg.create_task(service.run_forever(), name="heartbeat")

    def launch_outbox_relay(self, tg: asyncio.TaskGroup) -> None:
        relay = OutboxRelay(
            uow_factory=self._persistence.uow_factory,
            reader=self._persistence.outbox_reader,
            publisher=self._messaging.durable_publisher,
            clock=self._runtime.clock,
        )
        tg.create_task(relay.run_forever(), name="outbox-relay")

    def launch_fill_handler(self, tg: asyncio.TaskGroup) -> None:
        # One durable consumer across all exchanges. The filter_subject
        # ``ascent.exchange.*.responses`` matches every exchange's fill
        # channel. The ``*`` matches one token (the exchange UUID).
        consumer = NatsJetStreamConsumer(
            self._messaging.nc,
            stream="ASCENT_EXCHANGE",
            subject_filter="ascent.exchange.*.responses",
            durable_name="fill-handler",
        )
        service = FillHandlerService(
            consumer=consumer,
            processor=self._runtime.fill_processor,
            clock=self._runtime.clock,
        )
        tg.create_task(service.run_forever(), name="fill-handler")

    def launch_persister(
        self,
        tg: asyncio.TaskGroup,
        feed_records: dict[uuid.UUID, FeedRecord],
    ) -> None:
        channels = [record.model.channel for record in feed_records.values()]
        feed_to_output = {fid: record.model.output_table for fid, record in feed_records.items()}
        service = PersistenceService(
            feed_channels=channels,
            feed_id_to_output=feed_to_output,
            event_bus=self._messaging.event_bus,
            persister=self._runtime.persister,
        )
        tg.create_task(service.run_forever(), name="db-writer")

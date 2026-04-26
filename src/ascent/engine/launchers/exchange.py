"""Launches per-exchange services (dispatcher, fill loop, periodic reconciler)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ascent.adapters import ExchangeAdapter
from ascent.adapters.nats import NatsJetStreamConsumer
from ascent.application import (
    DispatcherService,
    ExchangeService,
    PeriodicReconciliationService,
)

if TYPE_CHECKING:
    from ascent.engine.contexts import (
        MessagingContext,
        PersistenceContext,
        RuntimeContext,
    )
    from ascent.exchanges.base import BaseExchange


class ExchangeLauncher:
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

    def launch(self, tg: asyncio.TaskGroup, exchange_cls: type[BaseExchange]) -> None:
        from ascent.database.models.exchanges import Exchange as ExchangeModel

        eid = self._runtime.deployment.exchange_ids[exchange_cls.ref()]
        with Session(self._persistence.engine) as db:
            record = db.get(ExchangeModel, eid)
        config = record.config if record else {}

        adapter = ExchangeAdapter(exchange_cls(config))
        dispatch_channel = f"ascent.exchange.{eid}"
        responses_channel = f"{dispatch_channel}.responses"

        # Dispatcher consumes dispatch intents from JetStream and forwards to
        # the exchange. Durable consumer name is per-exchange so restart
        # resumes the cursor.
        dispatch_consumer = NatsJetStreamConsumer(
            self._messaging.nc,
            stream="ASCENT_EXCHANGE",
            subject_filter=dispatch_channel,
            durable_name=f"dispatcher-{eid}",
        )
        # The dispatcher and exchange-fill loop both publish responses to
        # JetStream via the same durable publisher (msg_id keyed on
        # exchange_order_id + status dedups redeliveries).
        dispatcher = DispatcherService(
            exchange_id=eid,
            exchange=adapter,
            consumer=dispatch_consumer,
            responses_subject=responses_channel,
            responses_publisher=self._messaging.durable_publisher,
            clock=self._runtime.clock,
        )
        tg.create_task(dispatcher.run_forever(), name=f"dispatcher-{exchange_cls.__name__}")

        fill_service = ExchangeService(
            exchange_id=eid,
            exchange=adapter,
            responses_subject=responses_channel,
            responses_publisher=self._messaging.durable_publisher,
            reconciler=self._runtime.reconciler,
            clock=self._runtime.clock,
            open_orders=dispatcher.open_orders,
        )
        tg.create_task(fill_service.run_forever(), name=f"exchange-{exchange_cls.__name__}")

        # Layer-2 stuck-trade defense: re-run the reconciler every 5 minutes.
        # Catches any fill that slipped past the live stream/poll path.
        reconcile_service = PeriodicReconciliationService(
            reconciler=self._runtime.reconciler,
            exchange=adapter,
            exchange_id=eid,
            clock=self._runtime.clock,
            interval_seconds=300.0,
        )
        tg.create_task(
            reconcile_service.run_forever(),
            name=f"reconcile-{exchange_cls.__name__}",
        )

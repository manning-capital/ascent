"""PeriodicReconciliationService — defense-in-depth against stuck trades.

:class:`OrderReconciler` already synthesizes fill events for non-terminal
orders by pulling exchange state. Running it just once at startup handles
restart scenarios; running it on an interval handles the long tail — a
dropped fill event, a transient broker hiccup, any cause that left a trade
non-terminal when the exchange says otherwise.

The service wraps one reconciler + one exchange pair. The Runner wires up
one instance per exchange. Exceptions inside :meth:`OrderReconciler.reconcile`
are logged and swallowed so a transient failure on one tick doesn't kill
the loop.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from ascent.ports import Clock, ExchangePort

logger = logging.getLogger(__name__)


class _ReconcilerLike(Protocol):
    """Minimal duck-typed interface of :class:`OrderReconciler`.

    Defined here rather than importing the concrete class so tests can use
    a lightweight counting stub without bringing in the whole reconciler's
    dependency graph.
    """

    async def reconcile(
        self,
        *,
        exchange: ExchangePort,
        exchange_id: uuid.UUID,
        now,
    ) -> int: ...


@dataclass
class PeriodicReconciliationService:
    reconciler: _ReconcilerLike
    exchange: ExchangePort
    exchange_id: uuid.UUID
    clock: Clock
    interval_seconds: float = 300.0

    async def run_forever(self) -> None:
        logger.info(
            "PeriodicReconciliationService starting (exchange=%s, interval=%.1fs)",
            self.exchange_id,
            self.interval_seconds,
        )
        try:
            while True:
                # Run immediately on entry (and at the start of each loop
                # iteration) so startup doesn't wait a full interval to
                # heal anything stuck from the previous run.
                await self._reconcile_once()
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            logger.info("PeriodicReconciliationService %s cancelled", self.exchange_id)
            raise

    async def _reconcile_once(self) -> None:
        try:
            await self.reconciler.reconcile(
                exchange=self.exchange,
                exchange_id=self.exchange_id,
                now=self.clock.now(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # A transient failure (network blip, DB hiccup) must not kill
            # the loop — the whole point of this service is to keep
            # retrying until something sticks.
            logger.exception(
                "PeriodicReconciliationService: reconcile failed for exchange %s",
                self.exchange_id,
            )

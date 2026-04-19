"""OutboxRelay — poll the outbox table and forward rows to the durable broker.

Runs as a long-lived service. Each iteration:

1. Opens a UoW, claims up to ``batch_size`` unpublished rows with
   ``FOR UPDATE SKIP LOCKED``. Multiple relay workers can run concurrently
   without double-claiming.
2. Publishes each row to the :class:`DurablePublisher`, using the outbox
   row's id as the broker-side ``msg_id`` for dedup.
3. Marks the successfully-published rows as ``published_at=now()`` and
   commits the UoW. Rows whose publish raised stay unpublished — future
   iterations retry.

Crash safety:

- Crash between publish and ``mark_published``: the row stays unpublished,
  gets re-claimed by the next iteration, and the broker dedups on ``msg_id``.
  The shim publisher has no dedup, so during phase-4 downstream consumers
  may see duplicates; the JetStream publisher in phase-5 eliminates this.

The relay holds the UoW lock for the duration of the batch (claim → publish →
mark_published). For small batches with fast publishes this is fine; if
publish latency grows the batch size should shrink.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from ascent.ports import Clock, UnitOfWorkFactory
from ascent.ports.durable_publisher import DurablePublisher

logger = logging.getLogger(__name__)


class OutboxReader(Protocol):
    """Minimal interface the relay needs from an outbox reader.

    Defined here (rather than in ports/) because this is the relay's
    private contract — application code never calls these methods directly.
    """

    async def claim_batch(
        self,
        session,
        *,
        limit: int = 100,
        commit_visibility_lag_ms: int = 100,
    ) -> list: ...

    async def mark_published(
        self,
        session,
        *,
        ids,
        published_at,
    ) -> None: ...

    async def increment_attempts(
        self,
        session,
        *,
        ids,
    ) -> None: ...


@dataclass
class OutboxRelay:
    uow_factory: UnitOfWorkFactory
    reader: OutboxReader
    publisher: DurablePublisher
    clock: Clock
    poll_interval: float = 0.1
    batch_size: int = 100
    commit_visibility_lag_ms: int = 100

    async def run_forever(self) -> None:
        logger.info("OutboxRelay starting (batch_size=%d)", self.batch_size)
        try:
            while True:
                drained = await self.drain_once()
                if drained == 0:
                    await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.info("OutboxRelay cancelled")
            raise

    async def drain_once(self) -> int:
        """One claim-publish-mark pass. Returns the number of rows published.

        Kept as a separate method so tests can drive the relay one step at
        a time without running a forever-loop.
        """
        async with self.uow_factory() as uow:
            claimed = await self.reader.claim_batch(
                uow.session,
                limit=self.batch_size,
                commit_visibility_lag_ms=self.commit_visibility_lag_ms,
            )
            if not claimed:
                return 0

            published: list[tuple] = []
            failed: list[tuple] = []
            for row in claimed:
                try:
                    await self.publisher.publish(
                        row.subject,
                        row.payload,
                        msg_id=str(row.id),
                    )
                    published.append((row.id, row.created_at))
                except Exception:
                    logger.exception(
                        "OutboxRelay: publish failed for row id=%s (attempt %d)",
                        row.id,
                        row.attempts + 1,
                    )
                    failed.append((row.id, row.created_at))

            if published:
                await self.reader.mark_published(
                    uow.session,
                    ids=published,
                    published_at=self.clock.now(),
                )
            if failed:
                await self.reader.increment_attempts(uow.session, ids=failed)

            return len(published)

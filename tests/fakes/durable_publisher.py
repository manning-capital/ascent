"""In-memory :class:`DurablePublisher` fake for unit tests.

Records every ``publish`` call for inspection, and optionally dedups by
``msg_id`` so tests can model JetStream's dedup-window behavior without
spinning up NATS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _Published:
    subject: str
    payload: dict[str, Any]
    msg_id: str


class FakeDurablePublisher:
    """By default deduplicates by ``msg_id`` (mirrors JetStream). Pass
    ``dedup=False`` to model the Redis shim, which has no dedup.
    """

    def __init__(self, *, dedup: bool = True) -> None:
        self.dedup = dedup
        self.published: list[_Published] = []
        self._seen_ids: set[str] = set()
        # Test knob: if non-None, raise this exception on the next publish
        # and clear the knob. Lets tests simulate transient broker failures.
        self.fail_next: BaseException | None = None

    async def publish(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        msg_id: str,
    ) -> None:
        if self.fail_next is not None:
            err = self.fail_next
            self.fail_next = None
            raise err
        if self.dedup and msg_id in self._seen_ids:
            return
        self._seen_ids.add(msg_id)
        self.published.append(_Published(subject=subject, payload=payload, msg_id=msg_id))

    def subjects_seen(self) -> list[str]:
        return [p.subject for p in self.published]

    def payloads_for(self, subject: str) -> list[dict[str, Any]]:
        return [p.payload for p in self.published if p.subject == subject]

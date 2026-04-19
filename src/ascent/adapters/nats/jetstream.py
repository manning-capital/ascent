"""NATS JetStream adapters.

Implements:

- :class:`NatsJetStreamPublisher` — satisfies :class:`DurablePublisher` by
  publishing JSON-serialized payloads with ``Nats-Msg-Id`` for broker-side
  dedup (2-minute window by default; tune via ``duplicate_window`` on the
  stream).
- :class:`NatsJetStreamConsumer` — pull-based subscription. Yields
  :class:`NatsJetStreamMessage` wrappers that expose ``ack/nak/term``. The
  wrapper hides the library's ``Msg`` type from application code.
- :func:`ensure_stream` — idempotent provisioning. Safe to call on every
  startup; creates or updates the stream with the requested subjects and
  retention config.
- :func:`connect_nats` — thin wrapper around ``nats.connect`` with
  production-safe defaults (infinite reconnect, logging callbacks).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import nats
import nats.errors
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg
from nats.js.api import ConsumerConfig, RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import NotFoundError

from ascent.ports.durable_publisher import DurablePublisher

logger = logging.getLogger(__name__)


async def connect_nats(url: str, *, name: str | None = None) -> NatsClient:
    """Connect to a NATS server with production-safe reconnect defaults.

    Infinite reconnect keeps the engine alive through transient broker
    restarts; the error_cb logs disconnects so they stay visible.
    """

    async def _on_error(err: Exception) -> None:
        logger.error("NATS error: %s", err)

    async def _on_disconnected() -> None:
        logger.warning("NATS disconnected")

    async def _on_reconnected() -> None:
        logger.info("NATS reconnected")

    return await nats.connect(
        url,
        name=name or "ascent",
        max_reconnect_attempts=-1,
        reconnect_time_wait=2,
        error_cb=_on_error,
        disconnected_cb=_on_disconnected,
        reconnected_cb=_on_reconnected,
    )


async def ensure_stream(
    nc: NatsClient,
    *,
    stream_name: str,
    subjects: list[str],
    duplicate_window_seconds: int = 120,
    max_age_seconds: int | None = None,
) -> None:
    """Idempotently create or update the JetStream stream.

    ``duplicate_window_seconds`` controls how long the broker remembers
    ``Nats-Msg-Id`` values for dedup. Keep generous (default 2 min) so
    short crash/recover loops dedup cleanly; long windows cost memory on
    the broker.

    ``max_age_seconds`` bounds retention; None means retain until every
    consumer has acked (``RetentionPolicy.WORK_QUEUE``). We default to
    limits-based retention because multiple consumer groups read each
    message (dispatcher + audit, in the future).
    """
    js = nc.jetstream()
    # nats-py accepts durations as floats in seconds and handles the
    # JSON serialization to nanoseconds internally.
    cfg_kwargs: dict[str, Any] = {
        "name": stream_name,
        "subjects": subjects,
        "storage": StorageType.FILE,
        "retention": RetentionPolicy.LIMITS,
        "duplicate_window": float(duplicate_window_seconds),
    }
    if max_age_seconds is not None:
        cfg_kwargs["max_age"] = float(max_age_seconds)
    cfg = StreamConfig(**cfg_kwargs)
    try:
        await js.stream_info(stream_name)
        # Stream exists — update config in case subjects changed.
        await js.update_stream(cfg)
        logger.info("NATS stream '%s' updated", stream_name)
    except NotFoundError:
        await js.add_stream(cfg)
        logger.info("NATS stream '%s' created with subjects=%s", stream_name, subjects)


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


class NatsJetStreamPublisher(DurablePublisher):
    """Publish JSON payloads to JetStream with ``Nats-Msg-Id`` dedup.

    Instances are cheap; keep one per process and share it. The underlying
    ``jetstream()`` handle is reused across calls.
    """

    def __init__(self, nc: NatsClient) -> None:
        self._js = nc.jetstream()

    async def publish(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        msg_id: str,
    ) -> None:
        body = json.dumps(payload).encode()
        # The ``Nats-Msg-Id`` header is JetStream's dedup key. Two publishes
        # with the same id within the stream's ``duplicate_window`` collapse
        # to one delivered message — that's the crash-recovery story.
        await self._js.publish(subject, body, headers={"Nats-Msg-Id": msg_id})


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------


@dataclass
class NatsJetStreamMessage:
    """Application-facing message wrapper. Hides ``nats.aio.msg.Msg``."""

    subject: str
    payload: dict[str, Any]
    msg_id: str | None
    _raw: Msg

    async def ack(self) -> None:
        await self._raw.ack()

    async def nak(self) -> None:
        await self._raw.nak()

    async def term(self) -> None:
        await self._raw.term()


class NatsJetStreamConsumer:
    """Pull-based durable consumer.

    Pull mode avoids back-pressure surprises — the consumer asks for
    ``batch`` messages when it's ready, and an empty batch is a normal
    (not error) outcome that just means nothing's waiting. Push mode
    combined with slow handlers produces redelivery storms.

    ``durable_name`` must be stable across restarts for the broker to
    remember the consumer's cursor.
    """

    def __init__(
        self,
        nc: NatsClient,
        *,
        stream: str,
        subject_filter: str,
        durable_name: str,
        batch: int = 16,
        fetch_timeout: float = 1.0,
        max_deliver: int = 10,
        ack_wait_seconds: int = 30,
    ) -> None:
        self._nc = nc
        self._stream = stream
        self._subject_filter = subject_filter
        self._durable_name = durable_name
        self._batch = batch
        self._fetch_timeout = fetch_timeout
        self._max_deliver = max_deliver
        self._ack_wait_seconds = ack_wait_seconds
        self._subscription: Any = None
        self._closed = False
        # Messages left over from the last fetch — yielded one-by-one to the
        # iterator so we never silently drop batched messages.
        self._buffer: list[Msg] = []

    async def _ensure_subscribed(self) -> None:
        if self._subscription is not None:
            return
        js = self._nc.jetstream()
        # pull_subscribe is idempotent on the durable name — if the consumer
        # already exists on the server (e.g. from a previous process) it's
        # reused with its existing cursor.
        self._subscription = await js.pull_subscribe(
            self._subject_filter,
            durable=self._durable_name,
            stream=self._stream,
            config=ConsumerConfig(
                durable_name=self._durable_name,
                max_deliver=self._max_deliver,
                ack_wait=float(self._ack_wait_seconds),
                filter_subject=self._subject_filter,
            ),
        )

    def __aiter__(self) -> AsyncIterator[NatsJetStreamMessage]:
        return self

    async def __anext__(self) -> NatsJetStreamMessage:
        await self._ensure_subscribed()
        while not self._closed:
            if self._buffer:
                return _wrap(self._buffer.pop(0))
            try:
                msgs = await self._subscription.fetch(
                    batch=self._batch, timeout=self._fetch_timeout
                )
            except nats.errors.TimeoutError:
                # Normal: nothing to fetch within the timeout window. Loop.
                continue
            except Exception:
                logger.exception("NATS fetch error")
                continue
            self._buffer.extend(msgs)
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self._closed = True
        if self._subscription is not None:
            try:
                await self._subscription.unsubscribe()
            except Exception:
                logger.exception("NATS unsubscribe error")
            self._subscription = None


def _wrap(msg: Msg) -> NatsJetStreamMessage:
    payload: dict[str, Any]
    try:
        payload = json.loads(msg.data.decode())
    except Exception:
        logger.exception("NATS payload decode error on subject=%s", msg.subject)
        payload = {}
    headers = msg.header or {}
    return NatsJetStreamMessage(
        subject=msg.subject,
        payload=payload,
        msg_id=headers.get("Nats-Msg-Id"),
        _raw=msg,
    )

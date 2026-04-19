"""Integration tests for the NATS JetStream adapters against a real nats-server.

Uses the TestHarness's nats container. Exercises:
- Stream provisioning is idempotent.
- Publish + consume round-trip.
- ``Nats-Msg-Id`` dedup collapses duplicate publishes within the window.
- Consumer durable-name persistence: after aclose, a fresh consumer on the
  same durable name resumes from where we left off.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio

from ascent.adapters.nats import (
    NatsJetStreamConsumer,
    NatsJetStreamPublisher,
    connect_nats,
    ensure_stream,
)


@pytest_asyncio.fixture
async def nats_client(nats_url):
    nc = await connect_nats(nats_url, name="ascent-tests")
    try:
        yield nc
    finally:
        await nc.close()


@pytest.fixture
def stream_name() -> str:
    return f"ASCENT_TEST_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def _stream(nats_client, stream_name):
    await ensure_stream(
        nats_client,
        stream_name=stream_name,
        subjects=[f"ascent.test.{stream_name}.>"],
        duplicate_window_seconds=120,
    )
    yield stream_name
    try:
        await nats_client.jetstream().delete_stream(stream_name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_ensure_stream_is_idempotent(nats_client, stream_name):
    primary = [f"ascent.test.{stream_name}.primary.>"]
    await ensure_stream(nats_client, stream_name=stream_name, subjects=primary)
    # A second call with identical config must not raise.
    await ensure_stream(nats_client, stream_name=stream_name, subjects=primary)
    # And one with a **disjoint** expanded subject list should succeed
    # (it updates the stream — overlapping would fail per JetStream semantics).
    await ensure_stream(
        nats_client,
        stream_name=stream_name,
        subjects=primary + [f"ascent.test.{stream_name}.secondary.>"],
    )
    try:
        await nats_client.jetstream().delete_stream(stream_name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_publish_and_consume_round_trip(nats_client, _stream):
    publisher = NatsJetStreamPublisher(nats_client)
    subject = f"ascent.test.{_stream}.orders"

    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=_stream,
        subject_filter=subject,
        durable_name="round-trip",
        fetch_timeout=0.5,
    )

    await publisher.publish(subject, {"v": 1}, msg_id="m-1")
    await publisher.publish(subject, {"v": 2}, msg_id="m-2")

    received: list[dict] = []
    async for msg in consumer:
        received.append(msg.payload)
        await msg.ack()
        if len(received) == 2:
            break
    await consumer.aclose()

    assert received == [{"v": 1}, {"v": 2}]


@pytest.mark.asyncio
async def test_dedup_collapses_duplicate_msg_id(nats_client, _stream):
    publisher = NatsJetStreamPublisher(nats_client)
    subject = f"ascent.test.{_stream}.orders"

    for _ in range(3):
        # Same msg_id three times — JetStream should keep only the first.
        await publisher.publish(subject, {"v": 1}, msg_id="duplicate-me")

    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=_stream,
        subject_filter=subject,
        durable_name="dedup",
        fetch_timeout=0.3,
    )

    received: list[dict] = []
    # Fetch up to 3, but only 1 should exist.
    try:
        async with asyncio.timeout(2.0):
            async for msg in consumer:
                received.append(msg.payload)
                await msg.ack()
                if len(received) >= 2:  # bail early if we (wrongly) get more than 1
                    break
    except TimeoutError:
        pass
    await consumer.aclose()

    assert received == [{"v": 1}]


@pytest.mark.asyncio
async def test_durable_consumer_resumes_across_restart(nats_client, _stream):
    publisher = NatsJetStreamPublisher(nats_client)
    subject = f"ascent.test.{_stream}.orders"

    await publisher.publish(subject, {"v": 1}, msg_id="p-1")
    await publisher.publish(subject, {"v": 2}, msg_id="p-2")

    # First consumer — acks the first message and disconnects.
    c1 = NatsJetStreamConsumer(
        nats_client,
        stream=_stream,
        subject_filter=subject,
        durable_name="resume-test",
        fetch_timeout=0.3,
    )
    async for msg in c1:
        assert msg.payload == {"v": 1}
        await msg.ack()
        break
    await c1.aclose()

    # Second consumer — same durable name — must pick up v=2.
    c2 = NatsJetStreamConsumer(
        nats_client,
        stream=_stream,
        subject_filter=subject,
        durable_name="resume-test",
        fetch_timeout=0.3,
    )
    async for msg in c2:
        assert msg.payload == {"v": 2}
        await msg.ack()
        break
    await c2.aclose()


@pytest.mark.asyncio
async def test_nak_triggers_redelivery(nats_client, _stream):
    publisher = NatsJetStreamPublisher(nats_client)
    subject = f"ascent.test.{_stream}.orders"

    await publisher.publish(subject, {"v": 1}, msg_id="n-1")

    consumer = NatsJetStreamConsumer(
        nats_client,
        stream=_stream,
        subject_filter=subject,
        durable_name="nak-test",
        fetch_timeout=0.3,
        ack_wait_seconds=1,
    )

    # First attempt: nak — should be redelivered.
    first = await consumer.__anext__()
    assert first.payload == {"v": 1}
    await first.nak()

    # Second attempt: ack.
    second = await consumer.__anext__()
    assert second.payload == {"v": 1}
    await second.ack()

    await consumer.aclose()

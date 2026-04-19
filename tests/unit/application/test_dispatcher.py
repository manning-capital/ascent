"""Unit tests for :class:`DispatcherService`.

Drives the service via a :class:`FakeDurableConsumer` so we can assert on
ack/nak/term outcomes without a real broker. Success path acks; malformed
payload terms; unknown exception acks (to avoid a redelivery storm before
we have proper error classification).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ascent.application.dispatcher import DispatcherService
from tests.fakes import (
    FakeClock,
    FakeDurableConsumer,
    FakeDurablePublisher,
    FakeExchange,
)

NOW = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)


def _service() -> tuple[DispatcherService, FakeExchange, FakeDurableConsumer, FakeDurablePublisher]:
    exchange_id = uuid.uuid4()
    exchange = FakeExchange()
    consumer = FakeDurableConsumer()
    publisher = FakeDurablePublisher(dedup=True)
    service = DispatcherService(
        exchange_id=exchange_id,
        exchange=exchange,
        consumer=consumer,
        responses_subject=f"ascent.exchange.{exchange_id}.responses",
        responses_publisher=publisher,
        clock=FakeClock(NOW),
    )
    return service, exchange, consumer, publisher


def _submit_payload() -> dict:
    return {
        "action": "submit_order",
        "order_id": str(uuid.uuid4()),
        "trade_id": str(uuid.uuid4()),
        "trade_leg_id": str(uuid.uuid4()),
        "order": {
            "order_type": "MARKET",
            "side": "BUY",
            "from_asset_symbol": "BTC",
            "to_asset_symbol": "USD",
            "quantity": 1.0,
            "price": None,
        },
    }


@pytest.mark.asyncio
async def test_successful_submit_acks_and_publishes_response():
    service, exchange, consumer, publisher = _service()
    payload = _submit_payload()
    msg = consumer.feed("ascent.exchange.x", payload, msg_id="1")

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(msg._ack_event.wait(), timeout=1.0)
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(exchange.submissions) == 1
    assert msg._acked is True
    response_payloads = [
        p for p in publisher.published if p.payload.get("action") == "order_response"
    ]
    assert len(response_payloads) == 1


@pytest.mark.asyncio
async def test_successful_cancel_acks_and_publishes_update():
    service, exchange, consumer, publisher = _service()
    cancel_payload = {"action": "cancel_order", "exchange_order_id": "EX-123"}
    msg = consumer.feed("ascent.exchange.x", cancel_payload, msg_id="2")

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(msg._ack_event.wait(), timeout=1.0)
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert msg._acked is True
    updates = [p for p in publisher.published if p.payload.get("action") == "order_update"]
    assert len(updates) == 1


@pytest.mark.asyncio
async def test_unknown_action_is_termed():
    service, _, consumer, _ = _service()
    msg = consumer.feed("ascent.exchange.x", {"action": "do_something_weird"}, msg_id="3")

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(msg._term_event.wait(), timeout=1.0)
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert msg._termed is True
    assert msg._acked is False


@pytest.mark.asyncio
async def test_malformed_payload_is_termed():
    service, _, consumer, _ = _service()
    msg = consumer.feed("ascent.exchange.x", {"action": "submit_order"}, msg_id="4")

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(msg._term_event.wait(), timeout=1.0)
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert msg._termed is True


@pytest.mark.asyncio
async def test_submit_tracks_open_order():
    service, _, consumer, _ = _service()
    payload = _submit_payload()
    msg = consumer.feed("ascent.exchange.x", payload, msg_id="5")

    task = asyncio.create_task(service.run_forever())
    try:
        await asyncio.wait_for(msg._ack_event.wait(), timeout=1.0)
    finally:
        await consumer.aclose()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(service.open_orders) == 1

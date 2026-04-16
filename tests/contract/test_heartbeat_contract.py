"""Contract tests for :class:`ascent.ports.HeartbeatStore`."""

from __future__ import annotations

import uuid

import pytest


class TestTouchAndLiveness:
    @pytest.mark.asyncio
    async def test_touch_makes_entity_alive(self, heartbeat):
        eid = uuid.uuid4()
        assert not await heartbeat.is_alive("feed", eid)
        await heartbeat.touch("feed", eid, ttl_seconds=30)
        assert await heartbeat.is_alive("feed", eid)

    @pytest.mark.asyncio
    async def test_entity_types_isolated(self, heartbeat):
        """Touching ``feed/x`` must not mark ``strategy/x`` alive."""
        eid = uuid.uuid4()
        await heartbeat.touch("feed", eid)
        assert await heartbeat.is_alive("feed", eid)
        assert not await heartbeat.is_alive("strategy", eid)


class TestBatchStatuses:
    @pytest.mark.asyncio
    async def test_statuses_reports_per_entity(self, heartbeat):
        alive = uuid.uuid4()
        dead = uuid.uuid4()
        await heartbeat.touch("feed", alive)

        statuses = await heartbeat.statuses("feed", [alive, dead])
        assert statuses == {alive: True, dead: False}

    @pytest.mark.asyncio
    async def test_statuses_empty_input_returns_empty(self, heartbeat):
        assert await heartbeat.statuses("feed", []) == {}

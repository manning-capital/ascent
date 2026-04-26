"""Unit tests for :class:`FeedLauncher` branch selection.

The launcher picks between ``ScheduledFeedService`` (has ``schedule``),
``TriggeredFeedService`` (has ``depends_on`` but no schedule), or skipping
(streaming, or external feed with neither).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from unittest.mock import MagicMock

from ascent.engine.launchers.feed import FeedLauncher
from ascent.engine.queries import FeedRecord
from ascent.feeds.schedule import Schedule


class _FakeTaskGroup:
    def __init__(self) -> None:
        self.tasks: list[tuple[str, object]] = []

    def create_task(self, coro, *, name: str):
        # We never await the coro; close it so Python doesn't warn.
        coro.close()
        self.tasks.append((name, coro))
        return MagicMock()


def _make_feed_record(
    *,
    cls,
    feed_id: uuid.UUID,
    is_composite_scoped: bool = False,
    schedule: dict | None = None,
    parent_records: dict | None = None,
):
    model = MagicMock()
    model.id = feed_id
    model.feed_ref = cls.ref() if hasattr(cls, "ref") else "FEED"
    model.channel = f"ascent.feed.{model.feed_ref.lower()}"
    model.output_table = "feed_data"
    model.schedule = schedule
    model.parameters = {}
    return FeedRecord(
        cls=cls,
        model=model,
        parent_records=parent_records or {},
        is_composite_scoped=is_composite_scoped,
    )


def _make_launcher(feed_id: uuid.UUID, record: FeedRecord, feed_cls) -> FeedLauncher:
    persistence = MagicMock()
    persistence.session_factory = MagicMock()
    persistence.run_tracker = MagicMock()
    messaging = MagicMock()
    runtime = MagicMock()
    runtime.feed_records = {feed_id: record}
    runtime.deployment.feed_ids = {feed_cls.ref(): feed_id}
    runtime.executor = MagicMock()
    runtime.clock = MagicMock()
    return FeedLauncher(persistence=persistence, messaging=messaging, runtime=runtime)


def test_streaming_feed_is_skipped_with_warning(caplog):
    class _StreamingFeed:
        schedule = None
        depends_on: list[type] = []

        @classmethod
        def ref(cls):
            return "STREAMING_FEED"

        @classmethod
        def is_streaming(cls):
            return True

    feed_id = uuid.uuid4()
    record = _make_feed_record(cls=_StreamingFeed, feed_id=feed_id)
    launcher = _make_launcher(feed_id, record, _StreamingFeed)
    tg = _FakeTaskGroup()

    with caplog.at_level(logging.WARNING, logger="ascent.engine.launchers.feed"):
        launcher.launch(tg, _StreamingFeed)

    assert tg.tasks == []
    assert any("Streaming feed" in rec.getMessage() for rec in caplog.records)


def test_scheduled_feed_creates_scheduled_service_task():
    class _ScheduledFeed:
        schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
        depends_on: list[type] = []

        @classmethod
        def ref(cls):
            return "SCHEDULED_FEED"

        @classmethod
        def is_streaming(cls):
            return False

    feed_id = uuid.uuid4()
    record = _make_feed_record(
        cls=_ScheduledFeed,
        feed_id=feed_id,
        schedule={"interval": 1, "start_date": datetime(2024, 1, 1).isoformat()},
    )
    launcher = _make_launcher(feed_id, record, _ScheduledFeed)
    tg = _FakeTaskGroup()

    launcher.launch(tg, _ScheduledFeed)

    assert len(tg.tasks) == 1
    assert tg.tasks[0][0] == f"feed-{_ScheduledFeed.__name__}"


def test_triggered_feed_creates_triggered_service_task():
    class _ParentFeed:
        @classmethod
        def ref(cls):
            return "PARENT_FEED"

    class _TriggeredFeed:
        schedule = None
        depends_on = [_ParentFeed]

        @classmethod
        def ref(cls):
            return "TRIGGERED_FEED"

        @classmethod
        def is_streaming(cls):
            return False

    feed_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    parent_model = MagicMock()
    parent_model.id = parent_id
    parent_model.feed_ref = "PARENT_FEED"
    parent_model.channel = "ascent.feed.parent_feed"
    parent_model.schedule = {"interval": 2, "start_date": datetime(2024, 1, 1).isoformat()}

    record = _make_feed_record(
        cls=_TriggeredFeed,
        feed_id=feed_id,
        parent_records={parent_id: parent_model},
    )
    launcher = _make_launcher(feed_id, record, _TriggeredFeed)
    tg = _FakeTaskGroup()

    launcher.launch(tg, _TriggeredFeed)

    assert len(tg.tasks) == 1
    assert tg.tasks[0][0] == f"feed-{_TriggeredFeed.__name__}"


def test_external_feed_is_skipped(caplog):
    class _ExternalFeed:
        schedule = None
        depends_on: list[type] = []

        @classmethod
        def ref(cls):
            return "EXTERNAL_FEED"

        @classmethod
        def is_streaming(cls):
            return False

    feed_id = uuid.uuid4()
    record = _make_feed_record(cls=_ExternalFeed, feed_id=feed_id)
    launcher = _make_launcher(feed_id, record, _ExternalFeed)
    tg = _FakeTaskGroup()

    with caplog.at_level(logging.INFO, logger="ascent.engine.launchers.feed"):
        launcher.launch(tg, _ExternalFeed)

    assert tg.tasks == []
    assert any("is external" in rec.getMessage() for rec in caplog.records)

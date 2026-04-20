"""Snapshot-timestamp math — stateless, pure, no DB or IO.

Given a feed's ``Schedule``, compute the canonical snapshot timestamp that a
given wall-clock tick belongs to. This is the timestamp every persisted row
and every ``FeedRun`` is stamped with — it's how the engine aligns ticks to
the output table's ``timestamp`` column and how triggered feeds inherit a
parent's snapshot.

The previous ``FeedPartition`` concept is gone: there's no grid table, no
persisted windows, no PENDING/MATERIALIZED status. Just this function.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ascent.feeds.schedule import Schedule


def snapshot_timestamp_for(schedule: Schedule, dt: datetime) -> datetime:
    """Return the schedule-aligned boundary time that ``dt`` falls into.

    For sub-daily intervals (or daily without anchor): epoch-aligned boundaries.
    For daily+ intervals with anchor: anchor-aligned boundaries.
    """
    interval = schedule.interval
    anchor = schedule.anchor

    if anchor is not None and interval >= 86400:
        anchor_today = dt.replace(
            hour=anchor.hour,
            minute=anchor.minute,
            second=anchor.second,
            microsecond=0,
        )
        if anchor_today > dt:
            anchor_today -= timedelta(seconds=interval)
        return anchor_today

    epoch = dt.timestamp()
    boundary = (epoch // interval) * interval
    return datetime.fromtimestamp(boundary, tz=UTC)

"""Partition utilities — stateless math for computing partition keys and windows.

A partition is a discrete time window defined by a feed's schedule. The schedule's
``interval``, ``offset``, ``anchor``, and ``start_date`` fully determine the
partition grid. These functions are pure — no DB or IO access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ascent.feeds.schedule import Schedule


def partition_key_for(schedule: Schedule, dt: datetime) -> datetime:
    """Return the partition key (boundary time) that ``dt`` falls into.

    The partition key is the start of the interval window containing ``dt``.

    For sub-daily intervals (or daily without anchor): epoch-aligned boundaries.
    For daily+ intervals with anchor: anchor-aligned boundaries.
    """
    interval = schedule.interval
    anchor = schedule.anchor

    if anchor is not None and interval >= 86400:
        # Daily+ with anchor: find the most recent anchor occurrence <= dt
        anchor_today = dt.replace(
            hour=anchor.hour,
            minute=anchor.minute,
            second=anchor.second,
            microsecond=0,
        )
        if anchor_today > dt:
            anchor_today -= timedelta(seconds=interval)
        return anchor_today

    # Sub-daily or daily without anchor: epoch-aligned
    epoch = dt.timestamp()
    boundary = (epoch // interval) * interval
    return datetime.fromtimestamp(boundary, tz=UTC)


def partition_window(schedule: Schedule, key: datetime) -> tuple[datetime, datetime]:
    """Return ``(window_start, window_end)`` for a given partition key.

    The window is ``[key, key + interval)`` — inclusive start, exclusive end.
    """
    interval_td = timedelta(seconds=schedule.interval)
    return key, key + interval_td


def generate_keys(schedule: Schedule, start: datetime, end: datetime) -> list[datetime]:
    """Generate all partition keys in ``[start, end)``.

    Keys are generated from the schedule's ``start_date`` forward, filtered
    to the requested range. ``start`` must be >= ``schedule.start_date``.
    """
    effective_start = max(start, schedule.start_date)
    if effective_start >= end:
        return []

    # Find the first partition key >= effective_start
    first_key = partition_key_for(schedule, effective_start)
    if first_key < effective_start:
        first_key += timedelta(seconds=schedule.interval)

    keys: list[datetime] = []
    current = first_key
    interval_td = timedelta(seconds=schedule.interval)

    while current < end:
        keys.append(current)
        current += interval_td

    return keys


def find_gaps(
    schedule: Schedule,
    start: datetime,
    end: datetime,
    materialized_keys: set[datetime],
) -> list[datetime]:
    """Find partition keys in ``[start, end)`` that are not in ``materialized_keys``.

    Returns the list of missing (implicitly PENDING) partition keys.
    """
    all_keys = generate_keys(schedule, start, end)
    return [k for k in all_keys if k not in materialized_keys]

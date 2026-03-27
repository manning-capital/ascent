"""AlignedTimer — precision scheduling aligned to clock boundaries."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from ascent.feeds.schedule import Schedule

logger = logging.getLogger(__name__)

# Threshold for switching from sleep to busy-wait (seconds)
_BUSY_WAIT_THRESHOLD = 0.01  # 10ms


class AlignedTimer:
    """Precision scheduler that fires at clock-aligned boundaries.

    Supports intervals from 1 second to daily+.  Uses hybrid sleep + busy-wait
    for sub-second precision.

    Args:
        schedule: The Schedule defining interval, offset, and optional anchor.
    """

    def __init__(self, schedule: Schedule) -> None:
        self.schedule = schedule

    def next_tick(self, now: datetime) -> datetime:
        """Calculate the next execution time after ``now``.

        Sub-daily intervals are epoch-aligned + offset.
        Daily+ intervals with an anchor use anchor-aligned logic.
        """
        interval = self.schedule.interval
        offset = self.schedule.offset
        anchor = self.schedule.anchor

        if anchor is not None and interval >= 86400:
            # Daily+ with anchor: next occurrence of anchor time
            anchor_today = now.replace(
                hour=anchor.hour,
                minute=anchor.minute,
                second=anchor.second,
                microsecond=0,
            )
            # Apply offset
            target = anchor_today + timedelta(seconds=offset)
            if target <= now:
                target += timedelta(seconds=interval)
            return target

        # Sub-daily or daily without anchor: epoch-aligned
        epoch = now.timestamp()
        # Find the next boundary
        boundary = ((epoch // interval) + 1) * interval
        # Apply offset
        target_ts = boundary + offset
        # If the target is in the past (due to negative offset), advance
        if target_ts <= epoch:
            target_ts += interval
        return datetime.fromtimestamp(target_ts, tz=UTC)

    def wait_for_tick(self) -> datetime:
        """Block until the next tick using hybrid sleep + busy-wait.

        1. ``time.sleep()`` for the bulk of the wait (saves CPU)
        2. Spin loop for the final ~10ms (sub-second precision)

        If already past the tick (missed window): log warning, skip to next.

        Returns:
            The target tick time (as a datetime).
        """
        now = datetime.now(tz=UTC)
        target = self.next_tick(now)

        while True:
            remaining = (target - datetime.now(tz=UTC)).total_seconds()

            if remaining <= 0:
                # Missed the window — check if we're just barely past
                if remaining > -self.schedule.interval:
                    # Still within this tick's window, return it
                    return target
                # Completely missed — skip to next
                logger.warning(
                    "Missed tick at %s by %.3fs, skipping to next",
                    target.isoformat(),
                    abs(remaining),
                )
                target = self.next_tick(datetime.now(tz=UTC))
                continue

            if remaining > _BUSY_WAIT_THRESHOLD:
                # Sleep for most of the remaining time
                time.sleep(remaining - _BUSY_WAIT_THRESHOLD)
            else:
                # Busy-wait for final precision
                while datetime.now(tz=UTC) < target:
                    pass
                return target

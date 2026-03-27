"""Schedule model for feed timing configuration."""

from datetime import datetime, time

from pydantic import BaseModel, Field


class Schedule(BaseModel):
    """Defines when a scheduled feed fires and its partition boundaries.

    A feed has either a Schedule (timer-driven) or depends_on (triggered by
    parent feeds), not both.

    Examples::

        Schedule(interval=60, offset=-1.0, start_date=datetime(2024, 1, 1))
        Schedule(interval=300, offset=-2.0, start_date=datetime(2024, 1, 1))
        Schedule(interval=86400, anchor=time(0, 0), start_date=datetime(2024, 1, 1))
        Schedule(interval=1.0, start_date=datetime(2024, 6, 1))
    """

    interval: float = Field(
        ...,
        gt=0,
        description="Interval in seconds between ticks (1.0, 60.0, 3600.0, 86400.0, etc.)",
    )
    offset: float = Field(
        default=0.0,
        description=(
            "Seconds from the interval boundary. Negative values fire before the boundary "
            "(e.g., -1.0 fires 1s before the minute close)."
        ),
    )
    anchor: time | None = Field(
        default=None,
        description="Time-of-day anchor for daily+ intervals. Ignored for sub-daily intervals.",
    )
    start_date: datetime = Field(
        ...,
        description="Historical boundary — partitions begin at this time.",
    )

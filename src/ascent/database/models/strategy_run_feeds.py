"""Join table linking strategy runs to the feed runs active during execution."""

import datetime
import uuid

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.base import Base


class StrategyRunFeedRun(Base):
    __tablename__ = "strategy_run_feed_run"
    __table_args__ = {
        "comment": (
            "Links a strategy run to the feed runs that were active during its execution. "
            "The is_trigger flag identifies which feed event caused the strategy to evaluate."
        )
    }

    strategy_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy_run.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the strategy run",
    )
    feed_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed_run.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the feed run",
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("feed.id"),
        nullable=False,
        comment="The identifier of the feed (denormalized for efficient DAG lookups)",
    )
    is_trigger: Mapped[bool] = mapped_column(
        default=False,
        comment="Whether this feed event was the one that triggered the strategy evaluation",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of this link record",
    )

    strategy_run = relationship("StrategyRun", back_populates="feed_run_links")

    def __repr__(self):
        return (
            f"StrategyRunFeedRun(strategy_run_id={self.strategy_run_id}, "
            f"feed_run_id={self.feed_run_id}, is_trigger={self.is_trigger})"
        )

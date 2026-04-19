"""Transactional outbox row.

Persisted in the same DB transaction as the business write that triggered it.
A separate relay process polls for unpublished rows, forwards them to the
durable broker (JetStream), and marks them relayed. See
``docs/durable-messaging-and-plugin-contracts.md``.

TimescaleDB hypertable partitioned by ``created_at`` (daily chunks). The
primary key must include the partitioning column, hence ``(id, created_at)``.
Retention is consumer-guarded — chunks drop only after every consumer has
advanced past them (see ``ensure_hypertables``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ascent.database.models.base import Base


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    # Auto-increment bigint id; uniqueness within the hypertable is
    # enforced by (id, created_at). The sequence is shared across chunks.
    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Logical channel (what the use case thinks it's publishing to). Humans read this.
    channel: Mapped[str] = mapped_column(String(256), nullable=False)

    # JetStream subject the relay publishes on — typically equal to channel
    # but kept separate so we can evolve subject schemes without rewriting history.
    subject: Mapped[str] = mapped_column(String(256), nullable=False)

    # Arbitrary JSON payload.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # NULL until the relay has forwarded the row. Set to the publish time
    # so we can bound "how long did a row sit in the outbox" for alarms.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Number of publish attempts. Incremented on each relay pass. Used to
    # decide when to shove a row into a DLQ / stop retrying.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="event_outbox_pkey"),
        Index("ix_event_outbox_channel_time", "channel", "created_at", "id"),
        # Partial index on unpublished rows — the relay's hot query touches
        # this index exclusively, and it stays small because rows move out
        # of "unpublished" fast.
        Index(
            "ix_event_outbox_unpublished",
            "created_at",
            "id",
            postgresql_where=(published_at.is_(None)),
        ),
    )

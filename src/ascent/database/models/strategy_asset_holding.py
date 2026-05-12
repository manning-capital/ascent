"""StrategyAssetHolding — live, fill-driven snapshot of per-strategy positions.

Each row is one ``(strategy, exchange, asset, position_type)`` slot. Updated
inside the same UoW that records each fill (see
:class:`ascent.application.process_fill.FillProcessor`). The companion
:class:`Transaction` rows form the journal; this table is the rolled-up
snapshot for fast reads.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.exchanges import Exchange
from ascent.database.models.strategy import Strategy


class StrategyAssetHolding(Base):
    __tablename__ = "strategy_asset_holding"
    __table_args__ = {
        "comment": (
            "Live per-strategy position snapshot. Composite PK "
            "(strategy_id, exchange_id, asset_id, position_type) so future "
            "position types (STAKED, BORROWED, ...) extend without schema "
            "change. Quantity is signed only for asymmetric position types; "
            "for LONG / SHORT it stores the unsigned magnitude — direction "
            "lives in position_type."
        )
    }

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("strategy.id"),
        primary_key=True,
        nullable=False,
    )
    strategy: Mapped["Strategy"] = relationship("Strategy")
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange.id"),
        primary_key=True,
        nullable=False,
    )
    exchange: Mapped["Exchange"] = relationship("Exchange")
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
    )
    asset: Mapped["Asset"] = relationship("Asset")
    position_type: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        nullable=False,
        comment="PositionType enum value: LONG, SHORT, ...",
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(precision=28, scale=12),
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"StrategyAssetHolding(strategy_id={self.strategy_id}, "
            f"exchange_id={self.exchange_id}, asset_id={self.asset_id}, "
            f"position_type={self.position_type}, quantity={self.quantity})"
        )

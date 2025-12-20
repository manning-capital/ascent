import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, func, mapped_column, relationship

from summit.database.models.base import Base

if TYPE_CHECKING:
    from summit.database.models.transactions import PortfolioTransaction


class Portfolio(Base):
    __tablename__ = "portfolio"
    __table_args__ = {
        "comment": "The portfolio, represents a collection of assets and their transactions for tracking investment strategies and performance."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the portfolio"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="The name of the portfolio"
    )
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="The description of the portfolio"
    )
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the portfolio is active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the portfolio",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the portfolio",
    )

    # Relationship to transactions
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(
        "PortfolioTransaction", back_populates="portfolio"
    )

    def __repr__(self):
        return f"{Portfolio.__name__}({self.id}, {self.name})"

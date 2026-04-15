"""Cached name→UUID lookups for type tables.

Loaded once at startup so trade operations never query type tables per-trade.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.descriptors import Attribute
from ascent.database.models.types import OrderStatusType, OrderType, TradeStatusType

logger = logging.getLogger(__name__)


class TypeCache:
    """Loads and caches type table UUIDs at startup."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._order_types: dict[str, uuid.UUID] = {}
        self._order_status_types: dict[str, uuid.UUID] = {}
        self._trade_status_types: dict[str, uuid.UUID] = {}
        self._attributes: dict[uuid.UUID, str] = {}
        self._load(session_factory)

    def _load(self, session_factory: sessionmaker) -> None:
        with Session(bind=session_factory.kw["bind"]) as db:
            for row in db.execute(select(OrderType)).scalars():
                self._order_types[row.name] = row.id
            for row in db.execute(select(OrderStatusType)).scalars():
                self._order_status_types[row.name] = row.id
            for row in db.execute(select(TradeStatusType)).scalars():
                self._trade_status_types[row.name] = row.id
            for row in db.execute(select(Attribute)).scalars():
                self._attributes[row.id] = row.name.lower()

        logger.debug(
            "TypeCache loaded: %d order types, %d order status types, %d trade status types, %d attributes",
            len(self._order_types),
            len(self._order_status_types),
            len(self._trade_status_types),
            len(self._attributes),
        )

    def order_type_id(self, name: str) -> uuid.UUID:
        """Look up an OrderType UUID by name (e.g. 'MARKET')."""
        try:
            return self._order_types[name]
        except KeyError:
            raise ValueError(
                f"OrderType '{name}' not found. "
                f"Available: {', '.join(self._order_types)}. "
                f"Run 'ascent seed run --drop --profile base' to create type records."
            ) from None

    def order_status_type_id(self, name: str) -> uuid.UUID:
        """Look up an OrderStatusType UUID by name (e.g. 'SUBMITTED')."""
        try:
            return self._order_status_types[name]
        except KeyError:
            raise ValueError(
                f"OrderStatusType '{name}' not found. "
                f"Available: {', '.join(self._order_status_types)}."
            ) from None

    def trade_status_type_id(self, name: str) -> uuid.UUID:
        """Look up a TradeStatusType UUID by name (e.g. 'PENDING')."""
        try:
            return self._trade_status_types[name]
        except KeyError:
            raise ValueError(
                f"TradeStatusType '{name}' not found. "
                f"Available: {', '.join(self._trade_status_types)}."
            ) from None

    def trade_status_name(self, status_id: uuid.UUID) -> str | None:
        """Reverse-lookup: TradeStatusType UUID → name."""
        for name, uid in self._trade_status_types.items():
            if uid == status_id:
                return name
        return None

    def attribute_name(self, attr_id: uuid.UUID) -> str:
        """Look up an Attribute name by UUID (e.g. uuid → 'close')."""
        try:
            return self._attributes[attr_id]
        except KeyError:
            raise ValueError(
                f"Attribute with id '{attr_id}' not found. "
                f"Run 'ascent seed run --drop --profile base' to create attribute records."
            ) from None

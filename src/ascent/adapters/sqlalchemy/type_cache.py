"""TypeCache — adapter-internal enum↔UUID lookup for status/type tables.

Loaded once at adapter construction. The use cases and domain never see a
status-type UUID; mapping lives here at the edge.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ascent.database.models.descriptors import Attribute
from ascent.database.models.types import OrderStatusType, OrderType, TradeStatusType
from ascent.domain import OrderState, TradeState
from ascent.domain import OrderType as OrderTypeEnum

logger = logging.getLogger(__name__)


class TypeCache:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._order_type_to_id: dict[OrderTypeEnum, uuid.UUID] = {}
        self._order_state_to_id: dict[OrderState, uuid.UUID] = {}
        self._id_to_order_state: dict[uuid.UUID, OrderState] = {}
        self._trade_state_to_id: dict[TradeState, uuid.UUID] = {}
        self._id_to_trade_state: dict[uuid.UUID, TradeState] = {}
        self._attribute_name: dict[uuid.UUID, str] = {}
        self._attribute_id_by_name: dict[str, uuid.UUID] = {}
        self._load(session_factory)

    def _load(self, session_factory: sessionmaker) -> None:
        with Session(bind=session_factory.kw["bind"]) as db:
            for row in db.execute(select(OrderType)).scalars():
                try:
                    self._order_type_to_id[OrderTypeEnum(row.name)] = row.id
                except ValueError:
                    continue
            for row in db.execute(select(OrderStatusType)).scalars():
                try:
                    state = OrderState(row.name)
                except ValueError:
                    continue
                self._order_state_to_id[state] = row.id
                self._id_to_order_state[row.id] = state
            for row in db.execute(select(TradeStatusType)).scalars():
                try:
                    state = TradeState(row.name)
                except ValueError:
                    continue
                self._trade_state_to_id[state] = row.id
                self._id_to_trade_state[row.id] = state
            for row in db.execute(select(Attribute)).scalars():
                self._attribute_name[row.id] = row.name.lower()
                self._attribute_id_by_name[row.name] = row.id

    def order_type_id(self, order_type: OrderTypeEnum) -> uuid.UUID:
        return self._order_type_to_id[order_type]

    def order_state_id(self, state: OrderState) -> uuid.UUID:
        return self._order_state_to_id[state]

    def order_state_for_id(self, status_id: uuid.UUID | None) -> OrderState | None:
        if status_id is None:
            return None
        return self._id_to_order_state.get(status_id)

    def trade_state_id(self, state: TradeState) -> uuid.UUID:
        return self._trade_state_to_id[state]

    def trade_state_for_id(self, status_id: uuid.UUID | None) -> TradeState | None:
        if status_id is None:
            return None
        return self._id_to_trade_state.get(status_id)

    def attribute_name(self, attribute_id: uuid.UUID) -> str | None:
        return self._attribute_name.get(attribute_id)

    def attribute_id_for_name(self, name: str) -> uuid.UUID | None:
        return self._attribute_id_by_name.get(name)

    @property
    def attribute_map(self) -> dict[uuid.UUID, str]:
        return dict(self._attribute_name)

    @property
    def attribute_id_by_name(self) -> dict[str, uuid.UUID]:
        return dict(self._attribute_id_by_name)

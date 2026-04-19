import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UniverseItemCreate(BaseModel):
    instrument_id: uuid.UUID
    order: int


class ToggleActiveRequest(BaseModel):
    """PATCH body for disable/enable on any *_active flag."""

    is_active: bool


class BlockingTrade(BaseModel):
    """Open trade that prevents removal."""

    trade_id: uuid.UUID
    state: str
    instrument_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None
    direction: str | None = None
    quantity: float | None = None
    entry_at: str | None = None


class BlockingScopeItem(BaseModel):
    """Downstream scope item that depends on this row."""

    scope_type: Literal[
        "strategy_universe",
        "strategy_composite_universe",
        "feed_universe",
        "feed_composite_universe",
        "strategy_exchange",
    ]
    strategy_id: uuid.UUID | None = None
    feed_id: uuid.UUID | None = None
    exchange_id: uuid.UUID | None = None
    instrument_id: uuid.UUID | None = None
    composite_id: uuid.UUID | None = None
    display_name: str | None = None


class ImpactReport(BaseModel):
    """Returned by GET .../impact and embedded in 409 conflict bodies."""

    can_remove: bool
    reasons: list[str] = []
    blocking_trades: list[BlockingTrade] = []
    blocking_scope_items: list[BlockingScopeItem] = []
    suggested_action: Literal["remove", "disable", "clear_blockers"] = "remove"


class UniverseBatchAddInstruments(BaseModel):
    instrument_ids: list[uuid.UUID]
    start_order: int = 1


class UniverseItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    instrument_name: str | None = None
    instrument_display_name: str | None = None
    instrument_type_id: uuid.UUID | None = None
    is_active: bool = True
    order: int


class CompositeUniverseItemCreate(BaseModel):
    composite_id: uuid.UUID
    order: int


class CompositeUniverseBatchAdd(BaseModel):
    composite_ids: list[uuid.UUID]
    start_order: int = 1


class CompositeUniverseItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    composite_id: uuid.UUID
    composite_name: str | None = None
    composite_display_name: str | None = None
    composite_type_id: uuid.UUID | None = None
    is_active: bool = True
    order: int

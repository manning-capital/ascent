"""
Entity factory functions — pure data builders, no DB access.

Each function returns a dict of kwargs suitable for passing to the
corresponding SQLAlchemy model constructor. Used by both unit tests
(for mock data attributes) and integration fixtures (for session.add()).

All name fields use an auto-incrementing counter to ensure uniqueness.
Pass **overrides to customize any field.
"""

import uuid

_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"{_counter:04d}"


# ---------------------------------------------------------------------------
# Type factories
# ---------------------------------------------------------------------------


def make_asset_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"ASSET_TYPE_{n}",
        "display_name": f"Asset Type {n}",
        "description": f"Test asset type {n}",
    }
    defaults.update(overrides)
    return defaults


def make_provider_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"PROVIDER_TYPE_{n}",
        "display_name": f"Provider Type {n}",
        "description": f"Test provider type {n}",
    }
    defaults.update(overrides)
    return defaults


def make_instrument_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"INSTRUMENT_TYPE_{n}",
        "display_name": f"Instrument Type {n}",
        "description": f"Test instrument type {n}",
    }
    defaults.update(overrides)
    return defaults


def make_composite_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"COMPOSITE_TYPE_{n}",
        "display_name": f"Composite Type {n}",
        "description": f"Test composite type {n}",
        "min_members": 2,
        "max_members": 2,
    }
    defaults.update(overrides)
    return defaults


def make_trade_status_type(name: str, **overrides) -> dict:
    defaults = {
        "name": name,
        "display_name": name.title(),
        "description": f"{name} trade status",
    }
    defaults.update(overrides)
    return defaults


def make_order_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"ORDER_TYPE_{n}",
        "display_name": f"Order Type {n}",
        "description": f"Test order type {n}",
    }
    defaults.update(overrides)
    return defaults


def make_order_status_type(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"ORDER_STATUS_TYPE_{n}",
        "display_name": f"Order Status Type {n}",
        "description": f"Test order status type {n}",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Entity factories
# ---------------------------------------------------------------------------


def make_asset(asset_type_id: uuid.UUID, **overrides) -> dict:
    n = _next_id()
    defaults = {
        "asset_type_id": asset_type_id,
        "name": f"ASSET_{n}",
        "display_name": f"Asset {n}",
        "description": f"Test asset {n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_provider(provider_type_id: uuid.UUID, **overrides) -> dict:
    n = _next_id()
    defaults = {
        "provider_type_id": provider_type_id,
        "name": f"PROVIDER_{n}",
        "display_name": f"Provider {n}",
        "description": f"Test provider {n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_exchange(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"EXCHANGE_{n}",
        "display_name": f"Exchange {n}",
        "description": f"Test exchange {n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_instrument(
    instrument_type_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
    **overrides,
) -> dict:
    n = _next_id()
    defaults = {
        "instrument_type_id": instrument_type_id,
        "provider_id": provider_id,
        "from_asset_id": from_asset_id,
        "to_asset_id": to_asset_id,
        "name": f"INSTRUMENT_{n}",
        "display_name": f"Instrument {n}",
        "description": f"Test instrument {n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_instrument_member(
    instrument_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
    order: int = 1,
    **overrides,
) -> dict:
    defaults = {
        "instrument_id": instrument_id,
        "provider_id": provider_id,
        "from_asset_id": from_asset_id,
        "to_asset_id": to_asset_id,
        "order": order,
    }
    defaults.update(overrides)
    return defaults


def make_composite(composite_type_id: uuid.UUID, **overrides) -> dict:
    n = _next_id()
    defaults = {
        "composite_type_id": composite_type_id,
        "name": f"COMPOSITE_{n}",
        "display_name": f"Composite {n}",
        "description": f"Test composite {n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_composite_member(
    composite_id: uuid.UUID,
    instrument_id: uuid.UUID,
    order: int = 1,
    **overrides,
) -> dict:
    defaults = {
        "composite_id": composite_id,
        "instrument_id": instrument_id,
        "order": order,
    }
    defaults.update(overrides)
    return defaults


def make_feed(
    provider_id: uuid.UUID,
    instrument_type_id: uuid.UUID | None = None,
    composite_type_id: uuid.UUID | None = None,
    **overrides,
) -> dict:
    n = _next_id()
    defaults = {
        "provider_id": provider_id,
        "instrument_type_id": instrument_type_id,
        "composite_type_id": composite_type_id,
        "name": f"FEED_{n}",
        "display_name": f"Feed {n}",
        "description": f"Test feed {n}",
        "feed_ref": f"test.feed.{n}",
        "output_table": "instrument_attribute",
        "channel": f"ascent.feed.test.{n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_strategy(
    base_asset_id: uuid.UUID | None = None,
    **overrides,
) -> dict:
    n = _next_id()
    defaults = {
        "base_asset_id": base_asset_id,
        "name": f"STRATEGY_{n}",
        "display_name": f"Strategy {n}",
        "description": f"Test strategy {n}",
        "strategy_ref": f"test.strategy.{n}",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def make_trade(
    strategy_id: uuid.UUID,
    **overrides,
) -> dict:
    defaults = {
        "strategy_id": strategy_id,
        "is_paper": False,
    }
    defaults.update(overrides)
    return defaults


def make_trade_leg(
    trade_id: uuid.UUID,
    instrument_id: uuid.UUID,
    direction: str = "LONG",
    quantity: float = 1.0,
    **overrides,
) -> dict:
    defaults = {
        "trade_id": trade_id,
        "instrument_id": instrument_id,
        "direction": direction,
        "quantity": quantity,
    }
    defaults.update(overrides)
    return defaults


def make_attribute(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"ATTRIBUTE_{n}",
        "display_name": f"Attribute {n}",
        "description": f"Test attribute {n}",
    }
    defaults.update(overrides)
    return defaults


def make_metadata(**overrides) -> dict:
    n = _next_id()
    defaults = {
        "name": f"METADATA_{n}",
        "display_name": f"Metadata {n}",
        "description": f"Test metadata definition {n}",
        "value_type": "string",
    }
    defaults.update(overrides)
    return defaults

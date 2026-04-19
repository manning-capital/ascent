"""Exchange resolution service.

Resolves which exchange should handle a given instrument within a strategy's
configured exchange set. Used when creating trades to automatically determine
the execution venue for each trade leg.

Resolution is purely type-based: an exchange handles an instrument iff its
``(provider_id, instrument_type_id)`` matches the instrument's pair. When more
than one strategy exchange matches, the highest-priority one (lowest
``StrategyExchange.order``) wins.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import StrategyExchange
from ascent.database.models.composites import CompositeMember
from ascent.database.models.exchanges import Exchange
from ascent.database.models.instruments import Instrument
from ascent.server.exceptions import BadRequestError


def resolve_exchange_for_instrument(
    db: Session,
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> uuid.UUID:
    """Find the exchange that should handle a given instrument for a strategy.

    Picks the highest-priority strategy exchange whose
    ``(provider_id, instrument_type_id)`` matches the instrument.

    Raises BadRequestError if no matching exchange is found.
    """
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise BadRequestError(f"Instrument {instrument_id} not found")

    query = (
        select(StrategyExchange.exchange_id)
        .join(Exchange, Exchange.id == StrategyExchange.exchange_id)
        .where(StrategyExchange.strategy_id == strategy_id)
        .where(Exchange.provider_id == instrument.provider_id)
        .where(Exchange.instrument_type_id == instrument.instrument_type_id)
        .order_by(StrategyExchange.order.asc())
        .limit(1)
    )
    result = db.execute(query).scalar_one_or_none()

    if result is None:
        raise BadRequestError(
            f"No exchange configured for instrument {instrument_id} on strategy {strategy_id}. "
            "Add an exchange to this strategy whose provider and instrument type match the instrument."
        )

    return result


def resolve_exchanges_for_composite(
    db: Session,
    strategy_id: uuid.UUID,
    composite_id: uuid.UUID,
) -> dict[uuid.UUID, uuid.UUID]:
    """Resolve exchanges for all instruments in a composite.

    Returns a mapping of instrument_id -> exchange_id for each member of the composite.
    Raises BadRequestError if any member instrument cannot be resolved.
    """
    members = (
        db.execute(
            select(CompositeMember.instrument_id)
            .where(CompositeMember.composite_id == composite_id)
            .order_by(CompositeMember.order.asc())
        )
        .scalars()
        .all()
    )

    if not members:
        raise BadRequestError(f"Composite {composite_id} has no members")

    result: dict[uuid.UUID, uuid.UUID] = {}
    for instrument_id in members:
        result[instrument_id] = resolve_exchange_for_instrument(db, strategy_id, instrument_id)

    return result

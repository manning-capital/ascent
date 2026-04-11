"""Exchange resolution service.

Resolves which exchange should handle a given instrument within a strategy's
configured exchange set. Used when creating trades to automatically determine
the execution venue for each trade leg.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import ExchangeInstrumentScope, StrategyExchange
from ascent.database.models.composites import CompositeMember
from ascent.server.exceptions import BadRequestError


def resolve_exchange_for_instrument(
    db: Session,
    strategy_id: uuid.UUID,
    instrument_id: uuid.UUID,
) -> uuid.UUID:
    """Find the exchange that should handle a given instrument for a strategy.

    Resolution logic:
    1. Get all exchanges that have this instrument in their universe (ExchangeInstrumentScope)
    2. Get all exchanges this strategy is configured to use (StrategyExchange)
    3. Return the intersection, ordered by the StrategyExchange.order (priority)

    Raises BadRequestError if no matching exchange is found.
    """
    # Exchanges that have this instrument in their universe
    instrument_exchanges = select(ExchangeInstrumentScope.exchange_id).where(
        ExchangeInstrumentScope.instrument_id == instrument_id
    )

    # Intersect with strategy's configured exchanges, ordered by priority
    query = (
        select(StrategyExchange.exchange_id)
        .where(StrategyExchange.strategy_id == strategy_id)
        .where(StrategyExchange.exchange_id.in_(instrument_exchanges))
        .order_by(StrategyExchange.order.asc())
        .limit(1)
    )
    result = db.execute(query).scalar_one_or_none()

    if result is None:
        raise BadRequestError(
            f"No exchange configured for instrument {instrument_id} on strategy {strategy_id}. "
            "Ensure the instrument is in an exchange's universe and that exchange is linked to this strategy."
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
        result[instrument_id] = resolve_exchange_for_instrument(
            db, strategy_id, instrument_id
        )

    return result

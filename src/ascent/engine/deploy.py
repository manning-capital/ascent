"""Reusable deploy functions for registering feeds and strategies in the database.

These functions are the core logic extracted from ``ascent.cli.deploy``.
Both the CLI commands and the ``Runner.run()`` method call these to
create or update database records.

All functions use **upsert semantics**: create if missing, update schemas
if a record with the same ref already exists.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ascent.feeds.base import Feed
    from ascent.strategies.base import Strategy

logger = logging.getLogger(__name__)


def _resolve_id(
    db: Session,
    model: type,
    value: str | uuid.UUID | None,
    label: str,
) -> uuid.UUID | None:
    """Resolve a name or UUID string to a database UUID.

    Accepts a UUID (pass-through), a UUID string, or a name to look up.
    Returns ``None`` if *value* is ``None``.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    # Try parsing as UUID first
    try:
        return uuid.UUID(str(value))
    except ValueError:
        pass
    # Look up by name
    row = db.execute(select(model).where(model.name == value)).scalars().first()
    if row is None:
        raise ValueError(f"{label} '{value}' not found in database")
    return row.id


def _resolve_or_create_id(
    db: Session,
    model: type,
    value: str | uuid.UUID | None,
    label: str,
) -> uuid.UUID | None:
    """Resolve a name or UUID to a database UUID, creating the record if needed.

    Like ``_resolve_id`` but auto-creates a record when a name is given
    and no matching row exists.  Only works for models with ``name`` and
    ``display_name`` columns.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        pass
    row = db.execute(select(model).where(model.name == value)).scalars().first()
    if row is None:
        display = value.replace("_", " ").title()
        row = model(name=value, display_name=display)
        db.add(row)
        db.flush()
        logger.info("Auto-created %s '%s' (id=%s)", label, value, row.id)
    return row.id


def deploy_feed(
    feed_cls: type[Feed],
    db: Session,
    *,
    provider: str | uuid.UUID | None = None,
    instrument_type: str | uuid.UUID | None = None,
    composite_type: str | uuid.UUID | None = None,
    name: str | None = None,
) -> uuid.UUID:
    """Register or update a Feed class in the database.

    Creates a ``FeedModel`` record with the feed's schemas, schedule,
    and channel.  If a record with the same ``feed_ref`` already exists,
    updates its schemas in place.

    Also creates ``FeedDependency`` records for triggered feeds.

    The ``provider``, ``instrument_type``, and ``composite_type`` params
    accept either a UUID or a name string.  Class-level attributes on the
    Feed subclass are used as defaults when the caller doesn't pass them.

    Args:
        feed_cls: The Feed subclass to deploy.
        db: An open SQLAlchemy session (caller manages commit/rollback).
        name: Override display name.  Defaults to ``feed_cls.get_display_name()``.

    Returns:
        The database UUID of the feed record.
    """
    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.database.models.feeds import FeedDependency
    from ascent.database.models.providers import Provider
    from ascent.database.models.types import CompositeType, InstrumentType

    # Fall back to class-level attributes
    provider = provider or getattr(feed_cls, "provider", None)
    instrument_type = instrument_type or getattr(feed_cls, "instrument_type", None)
    composite_type = composite_type or getattr(feed_cls, "composite_type", None)

    # Resolve names/UUIDs
    provider_id = _resolve_id(db, Provider, provider, "Provider")
    instrument_type_id = _resolve_id(db, InstrumentType, instrument_type, "Instrument type")
    composite_type_id = _resolve_id(db, CompositeType, composite_type, "Composite type")

    # Validate required fields before touching the database
    missing = []
    if provider_id is None:
        missing.append("provider")
    if instrument_type_id is None and composite_type_id is None:
        missing.append("instrument_type or composite_type")
    if instrument_type_id is not None and composite_type_id is not None:
        raise ValueError(
            "Cannot specify both instrument_type and composite_type — "
            "a feed must target exactly one scope."
        )

    feed_name = feed_cls.get_name()
    display_name = name or feed_cls.get_display_name()
    param_schema = feed_cls.parameter_schema()
    data_schema = feed_cls.data_schema()
    output_table = feed_cls.output_table()
    schedule_dict = feed_cls.schedule.model_dump(mode="json") if feed_cls.schedule else None
    description = feed_cls.description or ""

    if missing:
        raise ValueError(
            f"Cannot deploy feed '{feed_name}': missing required field(s): {', '.join(missing)}"
        )

    existing = db.execute(select(FeedModel).where(FeedModel.name == feed_name)).scalars().first()

    if existing:
        existing.parameter_schema = param_schema
        existing.data_schema = data_schema
        existing.output_table = output_table
        existing.schedule = schedule_dict
        existing.provider_id = provider_id
        existing.instrument_type_id = instrument_type_id
        existing.composite_type_id = composite_type_id
        if name:
            existing.name = name
        if description:
            existing.description = description
        db.flush()
        feed_record = existing
        logger.info("Updated feed '%s' (id=%s)", feed_record.name, feed_record.id)
    else:
        feed_record = FeedModel(
            name=feed_name,
            display_name=display_name,
            description=description,
            provider_id=provider_id,
            instrument_type_id=instrument_type_id,
            composite_type_id=composite_type_id,
            feed_ref=feed_name,
            parameter_schema=param_schema,
            data_schema=data_schema,
            output_table=output_table,
            schedule=schedule_dict,
            channel="ascent.feed.placeholder",
            is_active=True,
        )
        db.add(feed_record)
        db.flush()
        # Update channel with actual ID
        feed_record.channel = f"ascent.feed.{feed_record.id}"
        db.flush()
        logger.info("Deployed feed '%s' (id=%s)", feed_record.name, feed_record.id)

    # Handle dependencies for triggered feeds
    if feed_cls.depends_on:
        for parent_cls in feed_cls.depends_on:
            parent_ref = parent_cls.ref()
            parent = (
                db.execute(select(FeedModel).where(FeedModel.feed_ref == parent_ref))
                .scalars()
                .first()
            )
            if parent:
                existing_dep = (
                    db.execute(
                        select(FeedDependency).where(
                            FeedDependency.feed_id == feed_record.id,
                            FeedDependency.depends_on_feed_id == parent.id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if not existing_dep:
                    dep = FeedDependency(
                        feed_id=feed_record.id,
                        depends_on_feed_id=parent.id,
                    )
                    db.add(dep)
                    db.flush()
                    logger.info("  Linked dependency: %s (id=%s)", parent_ref, parent.id)
            else:
                logger.warning("  Parent feed '%s' not found in DB. Deploy it first.", parent_ref)

    return feed_record.id


def deploy_strategy(
    strategy_cls: type[Strategy],
    db: Session,
    *,
    portfolio: str | uuid.UUID | None = None,
    name: str | None = None,
) -> uuid.UUID:
    """Register or update a Strategy class in the database.

    Creates a ``StrategyModel`` record with the strategy's schemas and
    parameters.  If a record with the same ``strategy_ref`` already exists,
    updates its schemas in place.

    Also creates ``StrategyFeed`` records for declared feed dependencies.

    The ``portfolio`` param accepts either a UUID or a name string.

    Args:
        strategy_cls: The Strategy subclass to deploy.
        db: An open SQLAlchemy session (caller manages commit/rollback).
        portfolio: Portfolio UUID or name.
        name: Override display name.  Defaults to ``strategy_cls.get_display_name()``.

    Returns:
        The database UUID of the strategy record.
    """
    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.database.models.feeds import StrategyFeed
    from ascent.database.models.portfolio import Portfolio
    from ascent.database.models.strategy import Strategy as StrategyModel

    # Fall back to class-level attribute
    portfolio = portfolio or getattr(strategy_cls, "portfolio", None)

    portfolio_id = _resolve_or_create_id(db, Portfolio, portfolio, "Portfolio")

    strategy_name = strategy_cls.get_name()
    display_name = name or strategy_cls.get_display_name()
    description = strategy_cls.description or ""
    param_schema = strategy_cls.parameter_schema()
    trade_view_config = strategy_cls.trade_view_config()
    defaults = strategy_cls.Parameters().model_dump()

    if portfolio_id is None:
        raise ValueError(
            f"Cannot deploy strategy '{strategy_name}': missing required field: portfolio"
        )

    existing = (
        db.execute(select(StrategyModel).where(StrategyModel.name == strategy_name))
        .scalars()
        .first()
    )

    if existing:
        existing.parameter_schema = param_schema
        existing.parameters = defaults
        existing.portfolio_id = portfolio_id
        existing.trade_view = trade_view_config
        if name:
            existing.display_name = name
        if description:
            existing.description = description
        db.flush()
        strat = existing
        logger.info("Updated strategy '%s' (id=%s)", strat.name, strat.id)
    else:
        strat = StrategyModel(
            name=strategy_name,
            display_name=display_name,
            description=description,
            strategy_ref=strategy_name,
            portfolio_id=portfolio_id,
            parameters=defaults,
            parameter_schema=param_schema,
            trade_view=trade_view_config,
            is_active=True,
        )
        db.add(strat)
        db.flush()
        logger.info("Deployed strategy '%s' (id=%s)", strat.name, strat.id)

    # Auto-create StrategyFeed records for declared feeds.
    # Each entry can be a Feed subclass, a name string, or a UUID.
    if strategy_cls.feeds:
        for order, feed_entry in enumerate(strategy_cls.feeds):
            if isinstance(feed_entry, str):
                # Resolve by name or UUID string
                feed_id = _resolve_id(db, FeedModel, feed_entry, "Feed")
                feed_record = db.get(FeedModel, feed_id) if feed_id else None
                feed_label = feed_entry
            else:
                # Feed subclass — look up by name
                feed_label = feed_entry.ref()
                feed_record = (
                    db.execute(select(FeedModel).where(FeedModel.name == feed_label))
                    .scalars()
                    .first()
                )
            if feed_record:
                existing_sf = (
                    db.execute(
                        select(StrategyFeed).where(
                            StrategyFeed.strategy_id == strat.id,
                            StrategyFeed.feed_id == feed_record.id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if not existing_sf:
                    sf = StrategyFeed(
                        strategy_id=strat.id,
                        feed_id=feed_record.id,
                        is_required=True,
                        order=order,
                    )
                    db.add(sf)
                    db.flush()
                    logger.info("  Linked feed: %s (id=%s)", feed_label, feed_record.id)
            else:
                logger.warning("  Feed '%s' not found in DB. Deploy it first.", feed_label)

    # Auto-create StrategyExchange records for declared exchanges.
    if strategy_cls.exchanges:
        from ascent.database.models.exchanges import Exchange as ExchangeModel
        from ascent.database.models.strategy import StrategyExchange

        for order, exchange_entry in enumerate(strategy_cls.exchanges):
            exchange_id = _resolve_id(db, ExchangeModel, exchange_entry, "Exchange")
            if exchange_id:
                existing_se = (
                    db.execute(
                        select(StrategyExchange).where(
                            StrategyExchange.strategy_id == strat.id,
                            StrategyExchange.exchange_id == exchange_id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if not existing_se:
                    se = StrategyExchange(
                        strategy_id=strat.id,
                        exchange_id=exchange_id,
                        order=order,
                    )
                    db.add(se)
                    db.flush()
                    logger.info("  Linked exchange: %s (id=%s)", exchange_entry, exchange_id)
            else:
                logger.warning("  Exchange '%s' not found in DB. Deploy it first.", exchange_entry)

    return strat.id


def deploy_exchange(
    exchange_cls: type,
    db: Session,
    *,
    provider: str | uuid.UUID | None = None,
    instrument_type: str | uuid.UUID | None = None,
    name: str | None = None,
    config: dict | None = None,
) -> uuid.UUID:
    """Register or update an Exchange class in the database.

    The ``provider`` and ``instrument_type`` params accept a UUID or name.
    Class-level attributes on the exchange subclass are used as defaults.

    Returns:
        The database UUID of the exchange record.
    """
    from ascent.database.models.exchanges import Exchange as ExchangeModel
    from ascent.database.models.providers import Provider
    from ascent.database.models.types import InstrumentType

    # Fall back to class-level attributes
    provider = provider or getattr(exchange_cls, "provider", None)
    instrument_type = instrument_type or getattr(exchange_cls, "instrument_type", None)
    config = config or getattr(exchange_cls, "config", None) or {}

    provider_id = _resolve_id(db, Provider, provider, "Provider")
    instrument_type_id = _resolve_id(db, InstrumentType, instrument_type, "Instrument type")

    import re

    exchange_name = name or re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", exchange_cls.__name__).upper()
    display_name = getattr(exchange_cls, "display_name", None) or re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])", " ", exchange_cls.__name__
    )
    description = getattr(exchange_cls, "description", None) or ""
    impl_class = f"{exchange_cls.__module__}:{exchange_cls.__name__}"

    existing = (
        db.execute(select(ExchangeModel).where(ExchangeModel.name == exchange_name))
        .scalars()
        .first()
    )

    if existing:
        existing.implementation_class = impl_class
        existing.config = config
        existing.provider_id = provider_id
        existing.instrument_type_id = instrument_type_id
        db.flush()
        logger.info("Updated exchange '%s' (id=%s)", existing.name, existing.id)
        return existing.id
    else:
        record = ExchangeModel(
            name=exchange_name,
            display_name=display_name,
            description=description,
            provider_id=provider_id,
            instrument_type_id=instrument_type_id,
            implementation_class=impl_class,
            config=config,
            is_active=True,
        )
        db.add(record)
        db.flush()
        logger.info("Deployed exchange '%s' (id=%s)", record.name, record.id)
        return record.id

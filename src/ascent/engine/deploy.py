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


def deploy_feed(
    feed_cls: type[Feed],
    db: Session,
    *,
    feed_type_id: uuid.UUID | None = None,
    provider_id: uuid.UUID | None = None,
    instrument_type_id: uuid.UUID | None = None,
    composite_type_id: uuid.UUID | None = None,
    name: str | None = None,
) -> uuid.UUID:
    """Register or update a Feed class in the database.

    Creates a ``FeedModel`` record with the feed's schemas, schedule,
    and channel.  If a record with the same ``feed_ref`` already exists,
    updates its schemas in place.

    Also creates ``FeedDependency`` records for triggered feeds.

    Args:
        feed_cls: The Feed subclass to deploy.
        db: An open SQLAlchemy session (caller manages commit/rollback).
        feed_type_id: Optional FK to the ``feed_type`` table.
        name: Override display name.  Defaults to ``feed_cls.get_display_name()``.

    Returns:
        The database UUID of the feed record.
    """
    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.database.models.feeds import FeedDependency

    canonical_ref = feed_cls.ref()
    display_name = name or feed_cls.get_display_name()
    param_schema = feed_cls.parameter_schema()
    data_schema = feed_cls.data_schema()
    output_table = feed_cls.output_table()
    schedule_dict = feed_cls.schedule.model_dump(mode="json") if feed_cls.schedule else None
    description = feed_cls.description or ""

    existing = (
        db.execute(select(FeedModel).where(FeedModel.feed_ref == canonical_ref)).scalars().first()
    )

    if existing:
        existing.parameter_schema = param_schema
        existing.data_schema = data_schema
        existing.output_table = output_table
        existing.schedule = schedule_dict
        if name:
            existing.name = name
        if description:
            existing.description = description
        db.flush()
        feed_record = existing
        logger.info("Updated feed '%s' (id=%s)", feed_record.name, feed_record.id)
    else:
        feed_record = FeedModel(
            name=display_name,
            display_name=display_name,
            description=description,
            feed_type_id=feed_type_id,
            provider_id=provider_id,
            instrument_type_id=instrument_type_id,
            composite_type_id=composite_type_id,
            feed_ref=canonical_ref,
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
    strategy_type_id: uuid.UUID | None = None,
    portfolio_id: uuid.UUID | None = None,
    name: str | None = None,
) -> uuid.UUID:
    """Register or update a Strategy class in the database.

    Creates a ``StrategyModel`` record with the strategy's schemas and
    parameters.  If a record with the same ``strategy_ref`` already exists,
    updates its schemas in place.

    Also creates ``StrategyFeed`` records for declared feed dependencies.

    Args:
        strategy_cls: The Strategy subclass to deploy.
        db: An open SQLAlchemy session (caller manages commit/rollback).
        strategy_type_id: Optional FK to the ``strategy_type`` table.
        portfolio_id: Optional FK to the ``portfolio`` table.
        name: Override display name.  Defaults to ``strategy_cls.get_display_name()``.

    Returns:
        The database UUID of the strategy record.
    """
    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.database.models.feeds import StrategyFeed
    from ascent.database.models.strategy import Strategy as StrategyModel

    canonical_ref = strategy_cls.ref()
    display_name = name or strategy_cls.get_display_name()
    description = strategy_cls.description or ""
    param_schema = strategy_cls.parameter_schema()
    defaults = strategy_cls.Parameters().model_dump()

    existing = (
        db.execute(select(StrategyModel).where(StrategyModel.strategy_ref == canonical_ref))
        .scalars()
        .first()
    )

    if existing:
        existing.parameter_schema = param_schema
        existing.parameters = defaults
        if name:
            existing.name = name
        if description:
            existing.description = description
        db.flush()
        strat = existing
        logger.info("Updated strategy '%s' (id=%s)", strat.name, strat.id)
    else:
        strat = StrategyModel(
            name=display_name,
            display_name=display_name,
            description=description,
            strategy_type_id=strategy_type_id,
            strategy_ref=canonical_ref,
            portfolio_id=portfolio_id,
            parameters=defaults,
            parameter_schema=param_schema,
            is_active=True,
        )
        db.add(strat)
        db.flush()
        logger.info("Deployed strategy '%s' (id=%s)", strat.name, strat.id)

    # Auto-create StrategyFeed records for declared feeds
    if strategy_cls.feeds:
        for order, feed_cls in enumerate(strategy_cls.feeds):
            feed_ref_str = feed_cls.ref()
            feed_record = (
                db.execute(select(FeedModel).where(FeedModel.feed_ref == feed_ref_str))
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
                    logger.info("  Linked feed: %s (id=%s)", feed_ref_str, feed_record.id)
            else:
                logger.warning("  Feed '%s' not found in DB. Deploy it first.", feed_ref_str)

    return strat.id

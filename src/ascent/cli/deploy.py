import uuid

import cyclopts

deploy = cyclopts.App(name="deploy", help="Deploy feeds and strategies to Ascent.")


def _import_ref(ref: str):
    """Import a module:name reference (e.g., 'ascent.feeds.examples.market:market_data')."""
    import importlib

    if ":" in ref:
        module_path, obj_name = ref.rsplit(":", 1)
    else:
        module_path, obj_name = ref.rsplit(".", 1)

    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


@deploy.command(name="feed")
def deploy_feed(
    feed_ref: str,
    *,
    name: str | None = None,
    database_url: str = "postgresql://localhost:5432/ascent",
    update: bool = False,
):
    """Deploy a feed to Ascent by registering it.

    Imports the feed function, extracts its Pandera schema and parameter
    schema, and creates a feed record in the database.

    Parameters
    ----------
    feed_ref
        Importable reference using colon syntax, e.g.
        ``ascent.feeds.examples.market:market_data``
    name
        Display name for the feed. Defaults to the feed's display_name.
    database_url
        PostgreSQL connection string.
    update
        If a feed with the same feed_ref exists, update it.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.feeds.decorator import Feed

    try:
        obj = _import_ref(feed_ref)
    except (ImportError, AttributeError) as e:
        print(f"Error: Could not import '{feed_ref}': {e}")
        return

    if not isinstance(obj, Feed):
        print(f"Error: '{feed_ref}' is not a @feed-decorated function.")
        return

    # Normalize ref to colon syntax
    canonical_ref = obj.ref

    display_name = name or obj.display_name
    param_schema = obj.parameter_schema()
    data_schema = obj.data_schema()
    output_table = obj.output_table()
    schedule_dict = obj.schedule.model_dump() if obj.schedule else None

    engine = create_engine(database_url)
    with Session(engine) as db:
        existing = (
            db.execute(select(FeedModel).where(FeedModel.feed_ref == canonical_ref))
            .scalars()
            .first()
        )

        if existing:
            if not update:
                print(f"Feed already exists: '{existing.name}' (id={existing.id})")
                print("Use --update to update.")
                return

            existing.parameter_schema = param_schema
            existing.data_schema = data_schema
            existing.output_table = output_table
            existing.schedule = schedule_dict
            if name:
                existing.name = name
            if obj.description:
                existing.description = obj.description
            db.commit()
            print(f"Updated feed '{existing.name}' (id={existing.id})")
        else:
            feed_record = FeedModel(
                name=display_name,
                description=obj.description,
                feed_ref=canonical_ref,
                parameter_schema=param_schema,
                data_schema=data_schema,
                output_table=output_table,
                schedule=schedule_dict,
                channel="ascent.feed.placeholder",
                is_active=True,
            )
            db.add(feed_record)
            db.commit()
            db.refresh(feed_record)
            # Update channel with actual ID
            feed_record.channel = f"ascent.feed.{feed_record.id}"
            db.commit()
            print(f"Deployed feed '{feed_record.name}' (id={feed_record.id})")

        # Handle dependencies for triggered feeds
        if obj.depends_on:
            from ascent.database.models.feeds import FeedDependency

            for parent_feed in obj.depends_on:
                parent_ref = f"{parent_feed.fetch_fn.__module__}:{parent_feed.fetch_fn.__name__}"
                parent = (
                    db.execute(select(FeedModel).where(FeedModel.feed_ref == parent_ref))
                    .scalars()
                    .first()
                )
                if parent:
                    existing_dep = (
                        db.execute(
                            select(FeedDependency).where(
                                FeedDependency.feed_id == (existing or feed_record).id,
                                FeedDependency.depends_on_feed_id == parent.id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if not existing_dep:
                        dep = FeedDependency(
                            feed_id=(existing or feed_record).id,
                            depends_on_feed_id=parent.id,
                        )
                        db.add(dep)
                        db.commit()
                        print(f"  Linked dependency: {parent_ref} (id={parent.id})")
                else:
                    print(f"  Warning: Parent feed '{parent_ref}' not found. Deploy it first.")

        print(f"  Feed: {canonical_ref}")
        print(f"  Output table: {output_table}")
        print(f"  Parameters: {len(param_schema.get('properties', {}))} fields")


@deploy.command(name="strategy")
def deploy_strategy(
    strategy_ref: str,
    *,
    name: str | None = None,
    portfolio_id: uuid.UUID | None = None,
    database_url: str = "postgresql://localhost:5432/ascent",
    update: bool = False,
):
    """Deploy a strategy to Ascent by registering it.

    Parameters
    ----------
    strategy_ref
        Importable reference to a Strategy subclass, e.g.
        ``ascent.strategies.examples.momentum.MomentumStrategy``.
    name
        Display name for the strategy. Defaults to the strategy's display_name.
    portfolio_id
        Portfolio to associate with the strategy.
    database_url
        PostgreSQL connection string.
    update
        If a strategy with the same ref exists, update it.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from ascent.database.models import Strategy as StrategyModel
    from ascent.strategies.base import Strategy as StrategyBase

    try:
        obj = _import_ref(strategy_ref)
    except (ImportError, AttributeError) as e:
        print(f"Error: Could not import '{strategy_ref}': {e}")
        return

    if not (isinstance(obj, type) and issubclass(obj, StrategyBase) and obj is not StrategyBase):
        print(f"Error: '{strategy_ref}' is not a Strategy subclass.")
        return

    canonical_ref = strategy_ref
    display_name = name or obj.get_display_name()
    description = obj.description
    param_schema = obj.parameter_schema()
    defaults = obj.Parameters().model_dump()

    engine = create_engine(database_url)
    with Session(engine) as db:
        existing = (
            db.execute(select(StrategyModel).where(StrategyModel.strategy_ref == canonical_ref))
            .scalars()
            .first()
        )

        if existing:
            if not update:
                print(f"Strategy already exists: '{existing.name}' (id={existing.id})")
                print("Use --update to update.")
                return

            existing.parameter_schema = param_schema
            existing.parameters = defaults
            if name:
                existing.name = name
            if description:
                existing.description = description
            db.commit()
            print(f"Updated strategy '{existing.name}' (id={existing.id})")
            strat = existing
        else:
            strat = StrategyModel(
                name=display_name,
                description=description,
                strategy_ref=canonical_ref,
                portfolio_id=portfolio_id,
                parameters=defaults,
                parameter_schema=param_schema,
                is_active=True,
            )
            db.add(strat)
            db.commit()
            db.refresh(strat)
            print(f"Deployed strategy '{strat.name}' (id={strat.id})")

        print(f"  Strategy: {canonical_ref}")
        print(f"  Parameters: {len(param_schema.get('properties', {}))} fields")
        for prop_name, prop in param_schema.get("properties", {}).items():
            prop_type = prop.get("type", prop.get("anyOf", "?"))
            default = defaults.get(prop_name, "—")
            print(f"    {prop_name}: {prop_type} = {default}")


@deploy.command(name="strategy-feed")
def deploy_strategy_feed(
    strategy_id: uuid.UUID,
    feed_id: uuid.UUID,
    *,
    is_required: bool = True,
    order: int = 0,
    database_url: str = "postgresql://localhost:5432/ascent",
):
    """Link a feed to a strategy manually.

    Parameters
    ----------
    strategy_id
        The strategy ID.
    feed_id
        The feed ID.
    is_required
        Whether this feed is required (AND logic) or optional (OR logic).
    order
        The order of the feed in the strategy's feed list.
    database_url
        PostgreSQL connection string.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from ascent.database.models.feeds import StrategyFeed

    engine = create_engine(database_url)
    with Session(engine) as db:
        existing = (
            db.execute(
                select(StrategyFeed).where(
                    StrategyFeed.strategy_id == strategy_id,
                    StrategyFeed.feed_id == feed_id,
                )
            )
            .scalars()
            .first()
        )

        if existing:
            print(f"Strategy-feed link already exists (strategy={strategy_id}, feed={feed_id})")
            return

        sf = StrategyFeed(
            strategy_id=strategy_id,
            feed_id=feed_id,
            is_required=is_required,
            order=order,
        )
        db.add(sf)
        db.commit()
        print(
            f"Linked feed {feed_id} to strategy {strategy_id} (required={is_required}, order={order})"
        )

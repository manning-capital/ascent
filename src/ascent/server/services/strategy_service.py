import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Strategy, StrategyRun, Trade, TradeStatusType
from ascent.database.models.feeds import Feed, FeedDependency, FeedRun, StrategyFeed
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.strategies import (
    StrategyCreate,
    StrategyDetail,
    StrategyFeedDAG,
    StrategyFeedNode,
    StrategyListItem,
    StrategyRunFeedRunItem,
    StrategyRunListItem,
    StrategyUpdate,
)


def _build_strategy_stats(db: Session, strategy_id: uuid.UUID) -> dict:
    total_trades = (
        db.execute(
            select(func.count()).select_from(Trade).where(Trade.strategy_id == strategy_id)
        ).scalar()
        or 0
    )

    open_trades = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(Trade.strategy_id == strategy_id)
            .where(TradeStatusType.symbol == "OPEN")
        ).scalar()
        or 0
    )

    closed_trades = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(Trade.strategy_id == strategy_id)
            .where(TradeStatusType.symbol == "CLOSED")
        ).scalar()
        or 0
    )

    wins = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(Trade.strategy_id == strategy_id)
            .where(TradeStatusType.symbol == "CLOSED")
            .where(Trade.total_realized_pnl > 0)
        ).scalar()
        or 0
    )

    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0

    total_pnl = (
        db.execute(
            select(func.coalesce(func.sum(Trade.total_realized_pnl), 0.0)).where(
                Trade.strategy_id == strategy_id
            )
        ).scalar()
        or 0.0
    )

    avg_win = (
        db.execute(
            select(func.avg(Trade.total_realized_pnl))
            .where(Trade.strategy_id == strategy_id)
            .where(Trade.total_realized_pnl > 0)
        ).scalar()
        or 0.0
    )

    avg_loss = (
        db.execute(
            select(func.avg(Trade.total_realized_pnl))
            .where(Trade.strategy_id == strategy_id)
            .where(Trade.total_realized_pnl < 0)
        ).scalar()
        or 0.0
    )

    last_trade_at = db.execute(
        select(func.max(Trade.entry_at)).where(Trade.strategy_id == strategy_id)
    ).scalar()

    return {
        "total_trades": total_trades,
        "open_trades": open_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(float(total_pnl), 2),
        "avg_win": round(float(avg_win), 2),
        "avg_loss": round(float(avg_loss), 2),
        "last_trade_at": last_trade_at,
    }


def get_strategies(db: Session) -> list[StrategyListItem]:
    query = select(Strategy).options(joinedload(Strategy.strategy_type))
    strategies = db.execute(query).unique().scalars().all()

    items = []
    for s in strategies:
        stats = _build_strategy_stats(db, s.id)
        items.append(
            StrategyListItem(
                id=s.id,
                name=s.name,
                description=s.description,
                strategy_type=s.strategy_type.name,
                strategy_class=s.strategy_ref,
                parameters=s.parameters,
                portfolio_id=s.portfolio_id,
                is_active=s.is_active,
                **stats,
            )
        )
    return items


def create_strategy(db: Session, data: StrategyCreate) -> Strategy:
    strategy = Strategy(**data.model_dump())
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(db: Session, strategy_id: uuid.UUID, data: StrategyUpdate) -> Strategy:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise NotFoundError("Strategy not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(strategy, key, value)
    db.commit()
    db.refresh(strategy)
    return strategy


def delete_strategy(db: Session, strategy_id: uuid.UUID) -> None:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise NotFoundError("Strategy not found")
    db.delete(strategy)
    db.commit()


def get_strategy_detail(db: Session, strategy_id: uuid.UUID) -> StrategyDetail:
    query = (
        select(Strategy)
        .where(Strategy.id == strategy_id)
        .options(joinedload(Strategy.strategy_type), joinedload(Strategy.portfolio))
    )
    strategy = db.execute(query).unique().scalars().first()
    if not strategy:
        raise NotFoundError("Strategy not found")

    stats = _build_strategy_stats(db, strategy.id)
    return StrategyDetail(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        strategy_type=strategy.strategy_type.name,
        strategy_class=strategy.strategy_ref,
        parameters=strategy.parameters,
        portfolio_id=strategy.portfolio_id,
        is_active=strategy.is_active,
        portfolio_name=strategy.portfolio.name if strategy.portfolio else None,
        parameter_schema=strategy.parameter_schema,
        created_at=strategy.created_at,
        **stats,
    )


def get_strategy_feed_dag(db: Session, strategy_id: uuid.UUID) -> StrategyFeedDAG:
    """Build the feed dependency DAG for a strategy."""
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise NotFoundError("Strategy not found")

    # Get direct strategy-feed links
    strategy_feeds = (
        db.execute(select(StrategyFeed).where(StrategyFeed.strategy_id == strategy_id))
        .scalars()
        .all()
    )

    if not strategy_feeds:
        return StrategyFeedDAG(nodes=[], edges=[])

    # Collect all feed IDs directly linked to the strategy
    direct_feed_ids = {sf.feed_id for sf in strategy_feeds}
    sf_map = {sf.feed_id: sf for sf in strategy_feeds}

    # Walk upstream dependencies to find all feeds in the DAG
    all_feed_ids = set(direct_feed_ids)
    queue = list(direct_feed_ids)
    all_edges: list[tuple[int, int]] = []

    while queue:
        current_id = queue.pop()
        deps = (
            db.execute(select(FeedDependency).where(FeedDependency.feed_id == current_id))
            .scalars()
            .all()
        )
        for dep in deps:
            all_edges.append((dep.depends_on_feed_id, dep.feed_id))
            if dep.depends_on_feed_id not in all_feed_ids:
                all_feed_ids.add(dep.depends_on_feed_id)
                queue.append(dep.depends_on_feed_id)

    # Load all feed records
    feeds = db.execute(select(Feed).where(Feed.id.in_(all_feed_ids))).scalars().all()
    feed_map = {f.id: f for f in feeds}

    # Build dependency lookup: feed_id -> list of parent feed IDs
    depends_on_map: dict[int, list[int]] = {fid: [] for fid in all_feed_ids}
    for parent_id, child_id in all_edges:
        depends_on_map[child_id].append(parent_id)

    # Get last run info for each feed
    last_run_map: dict[int, FeedRun | None] = {}
    for fid in all_feed_ids:
        last_run = (
            db.execute(
                select(FeedRun)
                .where(FeedRun.feed_id == fid)
                .order_by(FeedRun.started_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        last_run_map[fid] = last_run

    nodes = []
    for fid in all_feed_ids:
        f = feed_map[fid]
        sf = sf_map.get(fid)
        last_run = last_run_map.get(fid)
        nodes.append(
            StrategyFeedNode(
                id=f.id,
                name=f.name,
                description=f.description,
                feed_ref=f.feed_ref,
                is_active=f.is_active,
                schedule=f.schedule,
                channel=f.channel,
                is_required=sf.is_required if sf else True,
                order=sf.order if sf else 0,
                depends_on=depends_on_map.get(fid, []),
                last_run_status=last_run.status if last_run else None,
                last_run_at=last_run.started_at if last_run else None,
            )
        )

    return StrategyFeedDAG(nodes=nodes, edges=all_edges)


def get_strategy_runs(
    db: Session,
    strategy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    started_after: str | None = None,
    started_before: str | None = None,
) -> tuple[list[StrategyRunListItem], int]:
    base = select(StrategyRun).where(StrategyRun.strategy_id == strategy_id)
    count_base = (
        select(func.count()).select_from(StrategyRun).where(StrategyRun.strategy_id == strategy_id)
    )

    if started_after:
        dt = datetime.datetime.fromisoformat(started_after)
        base = base.where(StrategyRun.started_at >= dt)
        count_base = count_base.where(StrategyRun.started_at >= dt)
    if started_before:
        dt = datetime.datetime.fromisoformat(started_before)
        base = base.where(StrategyRun.started_at <= dt)
        count_base = count_base.where(StrategyRun.started_at <= dt)

    total = db.execute(count_base).scalar() or 0
    runs = (
        db.execute(
            base.options(joinedload(StrategyRun.feed_run_links))
            .order_by(StrategyRun.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .scalars()
        .all()
    )

    # Batch-load all referenced FeedRun statuses
    all_feed_run_ids = {link.feed_run_id for r in runs for link in r.feed_run_links}
    feed_run_status_map: dict[int, str] = {}
    if all_feed_run_ids:
        feed_runs = (
            db.execute(select(FeedRun).where(FeedRun.id.in_(all_feed_run_ids))).scalars().all()
        )
        feed_run_status_map = {fr.id: fr.status for fr in feed_runs}

    items = []
    for r in runs:
        feed_run_items = []
        trigger_feed_id = None
        for link in r.feed_run_links:
            feed_run_items.append(
                StrategyRunFeedRunItem(
                    feed_id=link.feed_id,
                    feed_run_id=link.feed_run_id,
                    is_trigger=link.is_trigger,
                    status=feed_run_status_map.get(link.feed_run_id, "UNKNOWN"),
                )
            )
            if link.is_trigger:
                trigger_feed_id = link.feed_id
        items.append(
            StrategyRunListItem(
                id=r.id,
                strategy_id=r.strategy_id,
                status=r.status,
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_message=r.error_message,
                feed_runs=feed_run_items,
                trigger_feed_id=trigger_feed_id,
            )
        )
    return items, total

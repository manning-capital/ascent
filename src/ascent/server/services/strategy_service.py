import datetime
import math
import statistics
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import Strategy, StrategyRun, Trade, TradeStatusType
from ascent.database.models.feeds import Feed, FeedDependency, FeedRun, StrategyFeed
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.strategies import (
    CumulativePnlPoint,
    PnlDistributionBin,
    StrategyCreate,
    StrategyDetail,
    StrategyFeedCreate,
    StrategyFeedDAG,
    StrategyFeedNode,
    StrategyListItem,
    StrategyRunFeedRunItem,
    StrategyRunListItem,
    StrategyStats,
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
            .where(TradeStatusType.name == "OPEN")
        ).scalar()
        or 0
    )

    closed_trades = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(Trade.strategy_id == strategy_id)
            .where(TradeStatusType.name == "CLOSED")
        ).scalar()
        or 0
    )

    wins = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(Trade.strategy_id == strategy_id)
            .where(TradeStatusType.name == "CLOSED")
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


def get_strategy_stats(db: Session, strategy_id: uuid.UUID) -> StrategyStats:
    """Compute comprehensive trade statistics for a strategy via SQL + Python."""
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise NotFoundError("Strategy not found")

    # ── Single aggregate query for core stats ──
    (
        select(Trade.id)
        .join(Trade.current_status_type)
        .where(Trade.strategy_id == strategy_id)
        .where(TradeStatusType.name == "CLOSED")
    ).correlate(None)

    agg = db.execute(
        select(
            func.count().label("total_trades"),
            func.coalesce(func.sum(Trade.total_realized_pnl), 0.0).label("total_pnl"),
            func.coalesce(func.sum(Trade.total_fees), 0.0).label("total_fees"),
            func.avg(Trade.total_realized_pnl).label("avg_pnl"),
            func.max(Trade.total_realized_pnl).label("max_win"),
            func.min(Trade.total_realized_pnl).label("max_loss"),
            func.count().filter(Trade.total_realized_pnl > 0).label("wins"),
            func.count().filter(Trade.total_realized_pnl < 0).label("losses"),
            func.count().filter(Trade.total_realized_pnl == 0).label("breakeven"),
            func.avg(Trade.total_realized_pnl)
            .filter(Trade.total_realized_pnl > 0)
            .label("avg_win"),
            func.avg(Trade.total_realized_pnl)
            .filter(Trade.total_realized_pnl < 0)
            .label("avg_loss"),
            func.sum(Trade.total_realized_pnl)
            .filter(Trade.total_realized_pnl > 0)
            .label("gross_win"),
            func.sum(Trade.total_realized_pnl)
            .filter(Trade.total_realized_pnl < 0)
            .label("gross_loss"),
        )
        .select_from(Trade)
        .join(Trade.current_status_type)
        .where(Trade.strategy_id == strategy_id)
        .where(TradeStatusType.name == "CLOSED")
    ).one()

    total_trades_all = (
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
            .where(TradeStatusType.name == "OPEN")
        ).scalar()
        or 0
    )

    closed_trades = agg.total_trades or 0
    wins = agg.wins or 0
    losses = agg.losses or 0
    breakeven = agg.breakeven or 0
    total_pnl = float(agg.total_pnl or 0)
    total_fees = float(agg.total_fees or 0)
    avg_win = float(agg.avg_win or 0)
    avg_loss = float(agg.avg_loss or 0)
    gross_win = float(agg.gross_win or 0)
    gross_loss = abs(float(agg.gross_loss or 0))

    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0
    payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0.0
    expectancy = (
        ((win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss) if closed_trades > 0 else 0.0
    )

    # ── Holding period averages via SQL ──
    avg_holding = db.execute(
        select(
            func.avg(func.extract("epoch", Trade.exit_at - Trade.entry_at)).label("avg_all"),
            func.avg(func.extract("epoch", Trade.exit_at - Trade.entry_at))
            .filter(Trade.total_realized_pnl > 0)
            .label("avg_wins"),
            func.avg(func.extract("epoch", Trade.exit_at - Trade.entry_at))
            .filter(Trade.total_realized_pnl < 0)
            .label("avg_losses"),
        )
        .select_from(Trade)
        .join(Trade.current_status_type)
        .where(Trade.strategy_id == strategy_id)
        .where(TradeStatusType.name == "CLOSED")
        .where(Trade.entry_at.is_not(None))
        .where(Trade.exit_at.is_not(None))
    ).one()

    # ── Fetch ordered PnL series for drawdown, streaks, distribution stats, and charts ──
    pnl_rows = db.execute(
        select(Trade.entry_at, Trade.total_realized_pnl)
        .join(Trade.current_status_type)
        .where(Trade.strategy_id == strategy_id)
        .where(TradeStatusType.name == "CLOSED")
        .where(Trade.total_realized_pnl.is_not(None))
        .order_by(Trade.entry_at.asc())
    ).all()

    pnls = [float(r.total_realized_pnl) for r in pnl_rows]

    # Median
    median_pnl = statistics.median(pnls) if pnls else 0.0

    # Std dev, skewness, kurtosis
    std_dev = 0.0
    skew = 0.0
    kurt = 0.0
    if len(pnls) >= 2:
        std_dev = statistics.stdev(pnls)
        mean = statistics.mean(pnls)
        if std_dev > 0 and len(pnls) >= 3:
            n = len(pnls)
            skew = sum(((v - mean) / std_dev) ** 3 for v in pnls) / n
        if std_dev > 0 and len(pnls) >= 4:
            n = len(pnls)
            kurt = sum(((v - mean) / std_dev) ** 4 for v in pnls) / n - 3

    # Sharpe & Sortino (per-trade)
    sharpe = 0.0
    sortino = 0.0
    if len(pnls) >= 2:
        mean = statistics.mean(pnls)
        if std_dev > 0:
            sharpe = mean / std_dev
        downside = [p for p in pnls if p < 0]
        if downside:
            downside_var = sum(p**2 for p in downside) / len(pnls)
            downside_dev = math.sqrt(downside_var)
            if downside_dev > 0:
                sortino = mean / downside_dev

    # Max drawdown
    max_dd = 0.0
    max_dd_duration = 0
    if pnls:
        peak = 0.0
        cumulative = 0.0
        dd_start = 0
        for i, p in enumerate(pnls):
            cumulative += p
            if cumulative > peak:
                peak = cumulative
                dd_start = i
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
                max_dd_duration = i - dd_start

    # Streaks
    max_win_streak = 0
    max_loss_streak = 0
    cur_win = 0
    cur_loss = 0
    for p in pnls:
        if p > 0:
            cur_win += 1
            cur_loss = 0
            max_win_streak = max(max_win_streak, cur_win)
        elif p < 0:
            cur_loss += 1
            cur_win = 0
            max_loss_streak = max(max_loss_streak, cur_loss)
        else:
            cur_win = 0
            cur_loss = 0

    # ── Chart data: cumulative PnL ──
    cumulative_pnl_points: list[CumulativePnlPoint] = []
    cum = 0.0
    for r in pnl_rows:
        cum += float(r.total_realized_pnl)
        cumulative_pnl_points.append(
            CumulativePnlPoint(
                date=r.entry_at.isoformat() if r.entry_at else "",
                value=round(cum, 2),
                symbol="",
            )
        )

    # ── Chart data: PnL distribution histogram ──
    pnl_distribution_bins: list[PnlDistributionBin] = []
    if pnls:
        pmin = min(pnls)
        pmax = max(pnls)
        n_bins = min(30, max(8, len(pnls) // 4))
        bin_width = (pmax - pmin) / n_bins if pmax != pmin else 1.0
        counts = [0] * n_bins
        for v in pnls:
            idx = int((v - pmin) / bin_width)
            if idx >= n_bins:
                idx = n_bins - 1
            counts[idx] += 1
        pnl_distribution_bins = [
            PnlDistributionBin(center=round(pmin + (i + 0.5) * bin_width, 2), count=c)
            for i, c in enumerate(counts)
        ]

    return StrategyStats(
        total_trades=total_trades_all,
        open_trades=open_trades,
        closed_trades=closed_trades,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=round(win_rate, 2),
        total_pnl=round(total_pnl, 2),
        total_fees=round(total_fees, 2),
        net_pnl=round(total_pnl - total_fees, 2),
        avg_trade_pnl=round(float(agg.avg_pnl or 0), 2),
        median_pnl=round(median_pnl, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        max_win=round(float(agg.max_win or 0), 2),
        max_loss=round(float(agg.max_loss or 0), 2),
        profit_factor=round(profit_factor, 2),
        payoff_ratio=round(payoff_ratio, 2),
        expectancy=round(expectancy, 2),
        sharpe_ratio=round(sharpe, 3),
        sortino_ratio=round(sortino, 3),
        max_drawdown=round(max_dd, 2),
        max_drawdown_duration=max_dd_duration,
        std_dev_pnl=round(std_dev, 2),
        skewness=round(skew, 3),
        kurtosis=round(kurt, 3),
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        avg_holding_seconds=round(float(avg_holding.avg_all), 1)
        if avg_holding.avg_all is not None
        else None,
        avg_holding_wins_seconds=round(float(avg_holding.avg_wins), 1)
        if avg_holding.avg_wins is not None
        else None,
        avg_holding_losses_seconds=round(float(avg_holding.avg_losses), 1)
        if avg_holding.avg_losses is not None
        else None,
        cumulative_pnl=cumulative_pnl_points,
        pnl_distribution=pnl_distribution_bins,
    )


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
                display_name=s.display_name,
                description=s.description,
                strategy_type=s.strategy_type.display_name,
                strategy_ref=s.strategy_ref,
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


def add_strategy_feed(
    db: Session, strategy_id: uuid.UUID, data: StrategyFeedCreate
) -> StrategyFeed:
    obj = StrategyFeed(
        strategy_id=strategy_id,
        feed_id=data.feed_id,
        is_required=data.is_required,
        order=data.order,
    )
    db.add(obj)
    db.commit()
    return obj


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
        display_name=strategy.display_name,
        description=strategy.description,
        strategy_type=strategy.strategy_type.display_name,
        strategy_ref=strategy.strategy_ref,
        parameters=strategy.parameters,
        portfolio_id=strategy.portfolio_id,
        is_active=strategy.is_active,
        portfolio_name=strategy.portfolio.display_name if strategy.portfolio else None,
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
    status: str | None = None,
) -> tuple[list[StrategyRunListItem], int]:
    base = select(StrategyRun).where(StrategyRun.strategy_id == strategy_id)
    count_base = (
        select(func.count()).select_from(StrategyRun).where(StrategyRun.strategy_id == strategy_id)
    )

    if status:
        base = base.where(StrategyRun.status == status)
        count_base = count_base.where(StrategyRun.status == status)
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


def get_strategy_run(db: Session, strategy_id: uuid.UUID, run_id: uuid.UUID) -> StrategyRunListItem:
    run = (
        db.execute(
            select(StrategyRun)
            .where(StrategyRun.id == run_id, StrategyRun.strategy_id == strategy_id)
            .options(joinedload(StrategyRun.feed_run_links))
        )
        .unique()
        .scalars()
        .first()
    )
    if not run:
        raise NotFoundError("Strategy run not found")

    feed_run_ids = {link.feed_run_id for link in run.feed_run_links}
    feed_run_status_map: dict[int, str] = {}
    if feed_run_ids:
        feed_runs = db.execute(select(FeedRun).where(FeedRun.id.in_(feed_run_ids))).scalars().all()
        feed_run_status_map = {fr.id: fr.status for fr in feed_runs}

    feed_run_items = []
    trigger_feed_id = None
    for link in run.feed_run_links:
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

    return StrategyRunListItem(
        id=run.id,
        strategy_id=run.strategy_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        feed_runs=feed_run_items,
        trigger_feed_id=trigger_feed_id,
    )

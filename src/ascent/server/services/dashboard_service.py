import datetime
import math
import statistics

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ascent.database.models import Strategy, Trade, TradeStatusType
from ascent.server.schemas.dashboard import DashboardStats
from ascent.server.schemas.strategies import CumulativePnlPoint


def get_dashboard_stats(db: Session) -> DashboardStats:
    # ── Strategy counts ──
    total_strategies = db.execute(select(func.count()).select_from(Strategy)).scalar() or 0
    active_strategies = (
        db.execute(
            select(func.count()).select_from(Strategy).where(Strategy.is_active.is_(True))
        ).scalar()
        or 0
    )

    # ── Total / open trade counts ──
    total_trades = db.execute(select(func.count()).select_from(Trade)).scalar() or 0
    open_trades = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(TradeStatusType.name == "OPEN")
        ).scalar()
        or 0
    )

    # ── Unrealized P&L for open trades ──
    total_unrealized_pnl = float(
        db.execute(
            select(func.coalesce(func.sum(Trade.total_unrealized_pnl), 0.0))
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(TradeStatusType.name == "OPEN")
        ).scalar()
        or 0.0
    )

    # ── Today P&L ──
    today = datetime.datetime.now(datetime.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl = float(
        db.execute(
            select(func.coalesce(func.sum(Trade.total_realized_pnl), 0.0)).where(
                Trade.exit_at >= today
            )
        ).scalar()
        or 0.0
    )

    # ── Composite aggregate query for closed trades ──
    agg = db.execute(
        select(
            func.count().label("total"),
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
        .where(TradeStatusType.name == "CLOSED")
    ).one()

    closed_trades = agg.total or 0
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

    # ── Holding period averages ──
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
        .where(TradeStatusType.name == "CLOSED")
        .where(Trade.entry_at.is_not(None))
        .where(Trade.exit_at.is_not(None))
    ).one()

    # ── Ordered PnL series for drawdown, streaks, distribution stats, and charts ──
    pnl_rows = db.execute(
        select(Trade.entry_at, Trade.total_realized_pnl)
        .join(Trade.current_status_type)
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

    # ── Chart data: cumulative P&L (ordered by exit_at — when PnL is realized) ──
    chart_rows = db.execute(
        select(Trade.exit_at, Trade.total_realized_pnl)
        .join(Trade.current_status_type)
        .where(TradeStatusType.name == "CLOSED")
        .where(Trade.total_realized_pnl.is_not(None))
        .where(Trade.exit_at.is_not(None))
        .order_by(Trade.exit_at.asc())
    ).all()
    cumulative_pnl_points: list[CumulativePnlPoint] = []
    cum = 0.0
    for r in chart_rows:
        cum += float(r.total_realized_pnl)
        cumulative_pnl_points.append(
            CumulativePnlPoint(
                date=r.exit_at.isoformat(),
                value=round(cum, 2),
                symbol="",
            )
        )

    return DashboardStats(
        total_strategies=total_strategies,
        active_strategies=active_strategies,
        total_trades=total_trades,
        open_trades=open_trades,
        closed_trades=closed_trades,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        total_pnl=round(total_pnl, 2),
        today_pnl=round(float(today_pnl), 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        total_fees=round(total_fees, 2),
        net_pnl=round(total_pnl - total_fees, 2),
        avg_trade_pnl=round(float(agg.avg_pnl or 0), 2),
        median_pnl=round(median_pnl, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        max_win=round(float(agg.max_win or 0), 2),
        max_loss=round(float(agg.max_loss or 0), 2),
        win_rate=round(win_rate, 2),
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
    )

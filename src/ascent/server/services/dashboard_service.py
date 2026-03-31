import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ascent.database.models import Strategy, Trade, TradeStatusType
from ascent.server.schemas.dashboard import DashboardStats


def get_dashboard_stats(db: Session) -> DashboardStats:
    total_strategies = db.execute(select(func.count()).select_from(Strategy)).scalar() or 0
    active_strategies = (
        db.execute(
            select(func.count()).select_from(Strategy).where(Strategy.is_active.is_(True))
        ).scalar()
        or 0
    )

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

    total_pnl = (
        db.execute(select(func.coalesce(func.sum(Trade.total_realized_pnl), 0.0))).scalar() or 0.0
    )

    today = datetime.datetime.now(datetime.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl = (
        db.execute(
            select(func.coalesce(func.sum(Trade.total_realized_pnl), 0.0)).where(
                Trade.exit_at >= today
            )
        ).scalar()
        or 0.0
    )

    closed_trades = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(TradeStatusType.name == "CLOSED")
        ).scalar()
        or 0
    )

    wins = (
        db.execute(
            select(func.count())
            .select_from(Trade)
            .join(Trade.current_status_type)
            .where(TradeStatusType.name == "CLOSED")
            .where(Trade.total_realized_pnl > 0)
        ).scalar()
        or 0
    )

    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0

    return DashboardStats(
        total_strategies=total_strategies,
        active_strategies=active_strategies,
        total_trades=total_trades,
        open_trades=open_trades,
        total_pnl=round(float(total_pnl), 2),
        today_pnl=round(float(today_pnl), 2),
        win_rate=round(win_rate, 2),
    )

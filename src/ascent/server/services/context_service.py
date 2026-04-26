"""Context-reconstruction service.

Given a strategy_run_id (MVP — feed_run / scope variants are follow-ups),
reconstruct what the strategy saw during that run by:


1. Walking the provenance chain ``StrategyRun → StrategyRunFeedRun → FeedRun``
2. Reading each ``FeedRun.context`` JSONB (the persisted ``Context``) for the
   table and scope-type spec
3. Resolving the as-of scope_ids from the bitemporal scope tables
4. (Optional) intersecting with the scope of a specific trade — its leg
   instruments and any composite whose members include those legs
5. Querying the appropriate attribute tables for rows in the trade window
6. Joining ``attribute`` (and ``period`` for period tables) for human-readable
   labels
7. Grouping rows into series and applying size caps
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models.composites import (
    Composite,
    CompositeAttribute,
    CompositeMember,
    CompositePeriodAttribute,
)
from ascent.database.models.descriptors import Attribute as AttributeRow
from ascent.database.models.descriptors import Period as PeriodRow
from ascent.database.models.feeds import (
    FeedCompositeScope,
    FeedInstrumentScope,
    FeedRun,
)
from ascent.database.models.instruments import (
    Instrument,
    InstrumentAttribute,
    InstrumentPeriodAttribute,
)
from ascent.database.models.strategy import Strategy as StrategyRow
from ascent.database.models.strategy import StrategyRun
from ascent.database.models.trades import Trade as TradeRow
from ascent.database.models.trades import TradeLeg as TradeLegRow
from ascent.domain import Attribute, Context, ContextSource, Period
from ascent.server.exceptions import NotFoundError
from ascent.server.schemas.context import (
    ContextResponse,
    ContextSeries,
    SeriesPoint,
    SeriesScopeRef,
    TradeViewSchema,
)

logger = logging.getLogger(__name__)

MAX_POINTS_PER_SERIES = 2000
MAX_TOTAL_POINTS = 20_000


_TABLE_CONFIG: dict[str, dict[str, Any]] = {
    "instrument_attribute": {
        "model": InstrumentAttribute,
        "scope_col": "instrument_id",
        "scope_model": Instrument,
        "has_period": False,
    },
    "instrument_period_attribute": {
        "model": InstrumentPeriodAttribute,
        "scope_col": "instrument_id",
        "scope_model": Instrument,
        "has_period": True,
    },
    "composite_attribute": {
        "model": CompositeAttribute,
        "scope_col": "composite_id",
        "scope_model": Composite,
        "has_period": False,
    },
    "composite_period_attribute": {
        "model": CompositePeriodAttribute,
        "scope_col": "composite_id",
        "scope_model": Composite,
        "has_period": True,
    },
}


def get_by_strategy_run(
    db: Session,
    strategy_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    series_filter: list[str] | None = None,
    trade_id: uuid.UUID | None = None,
) -> ContextResponse:
    """Reconstruct what a strategy run saw, anchored to ``run.snapshot_timestamp``.

    Default time window is ``[snapshot - 24h, snapshot]`` when start/end
    aren't supplied — trade-detail callers override with the trade's
    ``entry_at`` / ``exit_at``.

    When ``trade_id`` is provided, the result is filtered to the scope of
    that specific trade — only the leg instruments and composites whose
    members include those legs. Without this filter the response includes
    every scope_id the strategy's feeds touched, which is rarely what the
    UI wants.
    """
    t0 = time.perf_counter()
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

    trade_view = _load_trade_view(db, strategy_id)

    feed_run_ids = [link.feed_run_id for link in run.feed_run_links]
    if not feed_run_ids:
        return ContextResponse(
            context=Context(snapshot_timestamp=run.started_at, sources=[]),
            series=[],
            trade_view=trade_view,
        )

    feed_runs = db.execute(select(FeedRun).where(FeedRun.id.in_(feed_run_ids))).scalars().all()

    # Anchor: prefer the latest FeedRun snapshot — the run's logical "as of."
    snapshots = [fr.snapshot_timestamp for fr in feed_runs if fr.snapshot_timestamp]
    anchor = max(snapshots) if snapshots else run.started_at
    window_start = start if start is not None else anchor - timedelta(hours=24)
    # Default end follows the data: max of the run anchor and the explicit
    # ``start`` so an open trade whose entry_at trails the most-recent
    # FeedRun by a few seconds still gets a forward-looking window. For
    # open trades the chart should span ``[entry_at, now()]``.
    if end is not None:
        window_end = end
    else:
        window_end = max(anchor, datetime.now(tz=window_start.tzinfo))

    # Trade-scope filter: derive the instrument and composite ids the trade
    # actually touched. ``None`` means "no filter" (legacy behaviour).
    trade_filter = _resolve_trade_scope_filter(db, trade_id) if trade_id else None

    # Deduplicate (feed_id, scope_type) so we resolve scope and query the
    # attribute table once per unique source instead of per FeedRun. Scope
    # is read as-of the latest snapshot for that feed so all linked runs
    # share the same point-in-time view.
    sources_by_feed: dict[tuple[uuid.UUID, str], dict[str, Any]] = {}
    for feed_run in feed_runs:
        if feed_run.context is None:
            continue
        try:
            ctx = Context.model_validate(feed_run.context)
        except Exception:
            continue
        for source in ctx.sources:
            key = (feed_run.feed_id, source.scope_type)
            entry = sources_by_feed.get(key)
            if entry is None:
                entry = {
                    "feed_id": feed_run.feed_id,
                    "source": source,
                    "as_of": feed_run.snapshot_timestamp,
                    "feed_run_ids": {feed_run.id},
                }
                sources_by_feed[key] = entry
            else:
                entry["feed_run_ids"].add(feed_run.id)
                if feed_run.snapshot_timestamp > entry["as_of"]:
                    entry["as_of"] = feed_run.snapshot_timestamp
                    entry["source"] = source

    merged_sources: list[ContextSource] = []
    series_by_key: dict[tuple, ContextSeries] = {}
    series_feed_runs: dict[tuple, set[uuid.UUID]] = defaultdict(set)

    for entry in sources_by_feed.values():
        source: ContextSource = entry["source"]
        merged_sources.append(source)
        scope_ids = _resolve_feed_scope_as_of(
            db,
            feed_id=entry["feed_id"],
            scope_type=source.scope_type,
            as_of=entry["as_of"],
        )
        if trade_filter is not None:
            allowed = trade_filter[source.scope_type]
            scope_ids = [s for s in scope_ids if s in allowed]
        if not scope_ids:
            continue
        _collect_series(
            db,
            source=source,
            scope_ids=scope_ids,
            window_start=window_start,
            window_end=window_end,
            feed_run_ids=entry["feed_run_ids"],
            series_by_key=series_by_key,
            series_feed_runs=series_feed_runs,
        )

    # Apply size caps + filter
    series = list(series_by_key.values())
    if series_filter:
        wanted = set(series_filter)
        series = [s for s in series if s.name in wanted]
    series = _apply_size_caps(series)

    # Stamp source_feed_run_ids onto each series
    for s in series:
        s.source_feed_run_ids = sorted(
            series_feed_runs[(s.scope.id, s.attribute.id, s.period.id if s.period else None)]
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "context.get_by_strategy_run run_id=%s trade_id=%s feed_runs=%d unique_sources=%d "
        "series=%d elapsed_ms=%.0f",
        run_id,
        trade_id,
        len(feed_runs),
        len(sources_by_feed),
        len(series),
        elapsed_ms,
    )

    return ContextResponse(
        context=Context(snapshot_timestamp=anchor, sources=merged_sources),
        series=series,
        trade_view=trade_view,
    )


def _load_trade_view(db: Session, strategy_id: uuid.UUID) -> TradeViewSchema | None:
    """Read the persisted TradeView dict off the strategy row."""
    strategy = db.get(StrategyRow, strategy_id)
    if strategy is None or strategy.trade_view is None:
        return None
    try:
        return TradeViewSchema.model_validate(strategy.trade_view)
    except Exception:
        logger.warning("Invalid trade_view JSON on strategy %s; ignoring", strategy_id)
        return None


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_trade_scope_filter(db: Session, trade_id: uuid.UUID) -> dict[str, set[uuid.UUID]]:
    """Derive the scope of a specific trade.

    Returns ``{"instrument": {…}, "composite": {…}}`` — the instruments
    the trade has legs on, and the composite the trade was opened on.

    The composite is read directly from ``Trade.composite_id`` when set
    (the canonical, explicit attribution stamped at trade-time). If
    ``composite_id`` is null (instrument-scoped trade or pre-column data),
    we fall back to leg-membership inference: any composite whose member
    set fully contains the trade's leg instruments.
    """
    row = db.execute(select(TradeRow.composite_id).where(TradeRow.id == trade_id)).first()
    composite_id_explicit = row[0] if row else None

    leg_instrument_ids = list(
        db.execute(select(TradeLegRow.instrument_id).where(TradeLegRow.trade_id == trade_id))
        .scalars()
        .all()
    )

    composite_ids: set[uuid.UUID] = set()
    if composite_id_explicit is not None:
        composite_ids.add(composite_id_explicit)
    elif leg_instrument_ids:
        leg_count = len(set(leg_instrument_ids))
        composite_ids = set(
            db.execute(
                select(CompositeMember.composite_id)
                .where(CompositeMember.instrument_id.in_(leg_instrument_ids))
                .group_by(CompositeMember.composite_id)
                .having(func.count(CompositeMember.instrument_id.distinct()) == leg_count)
            )
            .scalars()
            .all()
        )

    return {
        "instrument": set(leg_instrument_ids),
        "composite": composite_ids,
    }


def _resolve_feed_scope_as_of(
    db: Session,
    *,
    feed_id: uuid.UUID,
    scope_type: str,
    as_of: datetime,
) -> list[uuid.UUID]:
    """Bitemporal as-of read of the feed's scope table."""
    if scope_type == "instrument":
        rows = db.execute(
            select(FeedInstrumentScope.instrument_id)
            .where(FeedInstrumentScope.feed_id == feed_id)
            .where(FeedInstrumentScope.added_at <= as_of)
            .where(
                or_(
                    FeedInstrumentScope.dropped_at.is_(None),
                    FeedInstrumentScope.dropped_at > as_of,
                )
            )
        ).all()
    else:
        rows = db.execute(
            select(FeedCompositeScope.composite_id)
            .where(FeedCompositeScope.feed_id == feed_id)
            .where(FeedCompositeScope.added_at <= as_of)
            .where(
                or_(
                    FeedCompositeScope.dropped_at.is_(None),
                    FeedCompositeScope.dropped_at > as_of,
                )
            )
        ).all()
    return [r[0] for r in rows]


def _collect_series(
    db: Session,
    *,
    source: ContextSource,
    scope_ids: list[uuid.UUID],
    window_start: datetime,
    window_end: datetime,
    feed_run_ids: set[uuid.UUID],
    series_by_key: dict[tuple, ContextSeries],
    series_feed_runs: dict[tuple, set[uuid.UUID]],
) -> None:
    cfg = _TABLE_CONFIG.get(source.table)
    if cfg is None:
        return
    model = cfg["model"]
    scope_col = cfg["scope_col"]
    scope_model = cfg["scope_model"]
    has_period = cfg["has_period"]

    cols: list[Any] = [
        model.timestamp,
        getattr(model, scope_col),
        model.attribute_id,
        model.attribute_value,
        AttributeRow.name.label("attr_name"),
        AttributeRow.display_name.label("attr_display_name"),
        scope_model.name.label("scope_name"),
        scope_model.display_name.label("scope_display_name"),
    ]
    if has_period:
        cols += [
            model.period_id,
            PeriodRow.name.label("period_name"),
            PeriodRow.display_name.label("period_display_name"),
            PeriodRow.duration_nanoseconds.label("period_duration_ns"),
        ]

    stmt = (
        select(*cols)
        .join(AttributeRow, AttributeRow.id == model.attribute_id)
        .join(scope_model, scope_model.id == getattr(model, scope_col))
        .where(getattr(model, scope_col).in_(scope_ids))
        .where(model.timestamp >= window_start)
        .where(model.timestamp <= window_end)
        .order_by(model.timestamp)
    )
    if has_period:
        stmt = stmt.join(PeriodRow, PeriodRow.id == model.period_id)

    rows = db.execute(stmt).all()
    if not rows:
        return

    scope_type = source.scope_type
    for row in rows:
        d = row._asdict() if hasattr(row, "_asdict") else dict(row._mapping)
        attr = Attribute(
            id=d["attribute_id"],
            name=d["attr_name"],
            display_name=d.get("attr_display_name"),
            period=(
                Period(
                    id=d["period_id"],
                    name=d["period_name"],
                    duration_nanoseconds=d.get("period_duration_ns"),
                )
                if has_period
                else None
            ),
        )
        scope_id = d[scope_col]
        scope_ref = SeriesScopeRef(
            type=scope_type,  # type: ignore[arg-type]
            id=scope_id,
            name=d.get("scope_name"),
            display_name=d.get("scope_display_name"),
        )
        period_token = f"[{attr.period.name}]" if attr.period else ""
        name = f"{attr.name}{period_token}@{scope_type}:{d.get('scope_name') or scope_id}"
        display_name_parts = [attr.display_name or attr.name]
        if attr.period:
            display_name_parts.append(attr.period.name)
        display_name_parts.append(
            d.get("scope_display_name") or d.get("scope_name") or str(scope_id)
        )
        display_name = " — ".join(display_name_parts)

        key = (scope_id, attr.id, attr.period.id if attr.period else None)
        series = series_by_key.get(key)
        if series is None:
            series = ContextSeries(
                name=name,
                display_name=display_name,
                attribute=attr,
                period=attr.period,
                scope=scope_ref,
                source_table=source.table,  # type: ignore[arg-type]
                source_feed_run_ids=[],  # filled at the end
                points=[],
            )
            series_by_key[key] = series
        series.points.append(SeriesPoint(t=d["timestamp"], v=d["attribute_value"]))
        series_feed_runs[key].update(feed_run_ids)


def _apply_size_caps(series: list[ContextSeries]) -> list[ContextSeries]:
    # Per-series stride downsample
    for s in series:
        if len(s.points) > MAX_POINTS_PER_SERIES:
            s.points = _stride_downsample(s.points, MAX_POINTS_PER_SERIES)
    # Global rebudget if total still exceeds
    total = sum(len(s.points) for s in series)
    if total <= MAX_TOTAL_POINTS:
        return series
    for s in series:
        budget = max(50, int(MAX_TOTAL_POINTS * len(s.points) / total))
        if len(s.points) > budget:
            s.points = _stride_downsample(s.points, budget)
    return series


def _stride_downsample(points: list[SeriesPoint], budget: int) -> list[SeriesPoint]:
    if budget >= len(points) or budget <= 1:
        return points
    stride = max(1, len(points) // budget)
    sampled = points[::stride]
    if sampled[-1] is not points[-1]:
        sampled.append(points[-1])
    return sampled

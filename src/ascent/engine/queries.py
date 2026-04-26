"""Startup-time read queries owned by the engine composition root.

These queries cross multiple ORM models (``Feed``, ``FeedDependency``,
``StrategyFeed``, ``StrategyExchange``, ``CompositeMember``, ``FeedScope*``)
and only run at boot. They don't belong on a domain-aligned repository
(wrong responsibility) nor on the launchers (which must stay DB-free for
unit testing), so they live here as a small read-model helper.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ascent.database.models.feeds import Feed as FeedModel
    from ascent.engine.deployer import Deployment
    from ascent.feeds.base import Feed

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedRecord:
    """Per-feed boot-time snapshot used by :class:`FeedLauncher`."""

    cls: type[Feed]
    model: FeedModel
    parent_records: dict[uuid.UUID, FeedModel]
    is_composite_scoped: bool


@dataclass(frozen=True)
class FeedSpecInfo:
    feed_id: uuid.UUID
    is_required: bool
    feed_ref: str
    channel: str
    is_composite_scoped: bool


@dataclass(frozen=True)
class StrategyInfo:
    """Per-strategy boot-time snapshot used by :class:`StrategyLauncher`."""

    parameters: dict
    portfolio_id: uuid.UUID
    feed_specs: list[FeedSpecInfo]
    exchanges: list[uuid.UUID]


class StartupQueries:
    """One-stop read-model for Runner's boot pipeline."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def load_feed_records(
        self,
        feeds: list[type[Feed]],
        deployment: Deployment,
    ) -> dict[uuid.UUID, FeedRecord]:
        from ascent.database.models.feeds import Feed as FeedModel
        from ascent.database.models.feeds import FeedDependency

        records: dict[uuid.UUID, FeedRecord] = {}
        with self._session_factory() as db:
            for feed_cls in feeds:
                fid = deployment.feed_ids[feed_cls.ref()]
                record = db.get(FeedModel, fid)
                if record is None:
                    continue
                deps = db.query(FeedDependency).filter(FeedDependency.feed_id == fid).all()
                parent_records = {
                    dep.depends_on_feed_id: db.get(FeedModel, dep.depends_on_feed_id)
                    for dep in deps
                }
                records[fid] = FeedRecord(
                    cls=feed_cls,
                    model=record,
                    parent_records=parent_records,
                    is_composite_scoped=record.composite_type_id is not None,
                )
        return records

    def load_strategy_info(self, strategy_id: uuid.UUID) -> StrategyInfo:
        from ascent.database.models.exchanges import Exchange as ExchangeModel
        from ascent.database.models.feeds import Feed as FeedModel
        from ascent.database.models.feeds import StrategyFeed
        from ascent.database.models.strategy import Strategy as StrategyModel
        from ascent.database.models.strategy import StrategyExchange

        with self._session_factory() as db:
            record = db.get(StrategyModel, strategy_id)
            if record is None:
                raise ValueError(f"Strategy {strategy_id} not found")

            feed_specs: list[FeedSpecInfo] = []
            sf_rows = (
                db.query(StrategyFeed)
                .filter(StrategyFeed.strategy_id == strategy_id)
                .order_by(StrategyFeed.order)
                .all()
            )
            for sf in sf_rows:
                feed = db.get(FeedModel, sf.feed_id)
                if feed is None:
                    continue
                feed_specs.append(
                    FeedSpecInfo(
                        feed_id=feed.id,
                        is_required=sf.is_required,
                        feed_ref=feed.feed_ref,
                        channel=feed.channel,
                        is_composite_scoped=feed.composite_type_id is not None,
                    )
                )

            exchanges: list[uuid.UUID] = []
            se_rows = (
                db.query(StrategyExchange)
                .filter(StrategyExchange.strategy_id == strategy_id)
                .order_by(StrategyExchange.order)
                .all()
            )
            for se in se_rows:
                ex = db.get(ExchangeModel, se.exchange_id)
                if ex and ex.is_active:
                    exchanges.append(ex.id)

            return StrategyInfo(
                parameters=record.parameters or {},
                portfolio_id=record.portfolio_id,
                feed_specs=feed_specs,
                exchanges=exchanges,
            )

    def load_composite_members(self) -> dict[uuid.UUID, list[uuid.UUID]]:
        """Ordered instrument members for every composite in the database.

        Composite-scoped strategies use this to build the
        ``(composite_id, instrument_id)`` MultiIndex behind ``ctx.df``.
        """
        from ascent.database.models.composites import CompositeMember

        members: dict[uuid.UUID, list[uuid.UUID]] = {}
        with self._session_factory() as db:
            rows = (
                db.query(CompositeMember)
                .order_by(CompositeMember.composite_id, CompositeMember.order)
                .all()
            )
            for row in rows:
                members.setdefault(row.composite_id, []).append(row.instrument_id)
        return members

    def reconcile_universes(self, deployment: Deployment) -> None:
        """Auto-disable drifted strategy-universe items; log one line per item."""
        from ascent.server.services.universe_service import reconcile_strategy_universe

        with self._session_factory() as db:
            for sid in deployment.strategy_ids.values():
                drift = reconcile_strategy_universe(db, sid)
                for item in drift:
                    logger.warning(
                        "Auto-disabled drifted %s item %s on strategy %s: %s",
                        item.scope_type,
                        item.item_id,
                        item.strategy_id,
                        item.reason,
                    )

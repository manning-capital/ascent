"""Deploy registered feed/strategy/exchange classes to the database.

Wraps the existing :mod:`ascent.engine.deploy` functions in a class so the
Runner has one collaborator to call and so the returned :class:`Deployment`
becomes a public named type rather than a module-private ``_Deployment``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ascent.engine.deploy import deploy_exchange, deploy_feed, deploy_strategy
from ascent.engine.sorting import _topological_sort_feeds

if TYPE_CHECKING:
    from ascent.exchanges.base import BaseExchange
    from ascent.feeds.base import Feed
    from ascent.strategies.base import Strategy


@dataclass(frozen=True)
class Deployment:
    feed_ids: dict[str, uuid.UUID]
    strategy_ids: dict[str, uuid.UUID]
    exchange_ids: dict[str, uuid.UUID]


class Deployer:
    def __init__(
        self,
        feeds: list[type[Feed]],
        strategies: list[type[Strategy]],
        exchanges: list[type[BaseExchange]],
    ) -> None:
        self._feeds = feeds
        self._strategies = strategies
        self._exchanges = exchanges

    def deploy(self, engine) -> Deployment:
        """Register every class in a single transaction and return its IDs.

        Feeds are deployed in topological order so ``FeedDependency`` rows
        can reference already-inserted parents.
        """
        sorted_feeds = _topological_sort_feeds(self._feeds)
        feed_ids: dict[str, uuid.UUID] = {}
        strategy_ids: dict[str, uuid.UUID] = {}
        exchange_ids: dict[str, uuid.UUID] = {}
        with Session(engine) as db:
            for feed_cls in sorted_feeds:
                feed_ids[feed_cls.ref()] = deploy_feed(feed_cls, db)
            for strategy_cls in self._strategies:
                strategy_ids[strategy_cls.ref()] = deploy_strategy(strategy_cls, db)
            for exchange_cls in self._exchanges:
                exchange_ids[exchange_cls.ref()] = deploy_exchange(exchange_cls, db)
            db.commit()
        return Deployment(feed_ids, strategy_ids, exchange_ids)

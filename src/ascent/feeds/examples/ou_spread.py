"""OU spread feed.

Triggered by :class:`OUParams` and :class:`MarketData`. On each tick this
feed reads the latest hedge ratio per composite and the latest CLOSE prices
per instrument, and publishes the per-composite log-spread
``s = ln(p_a) - beta * ln(p_b)`` as the ``OU_SPREAD`` attribute.

Without this feed the spread is computed transiently inside
``OUStrategy.derive()`` and discarded, so the trade-detail context chart has
no spread series to plot.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import ClassVar

import pandas as pd
from pandera.typing.pandas import DataFrame
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds import Feed
from ascent.feeds.examples.market import MarketData
from ascent.feeds.examples.ou_params import OUParams
from ascent.feeds.output import CompositeAttributes


class OUSpread(Feed):
    """Emits the per-composite log-spread driven by OU parameters and market prices."""

    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    depends_on = [OUParams, MarketData]
    display_name = "OU Spread"
    description = (
        "Per-tick log-spread s = ln(p_a) - beta*ln(p_b) per composite, derived "
        "from OUParams (OU_BETA) and MarketData (CLOSE)."
    )

    _composite_legs: ClassVar[dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]]] = {}
    _initialised: ClassVar[bool] = False

    def _ensure_initialised(self) -> None:
        if OUSpread._initialised:
            return
        from ascent.database.models.composites import Composite, CompositeMember
        from ascent.database.models.types import CompositeType

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(Composite.id, CompositeMember.order, CompositeMember.instrument_id)
                .join(CompositeType, Composite.composite_type_id == CompositeType.id)
                .join(CompositeMember, CompositeMember.composite_id == Composite.id)
                .where(CompositeType.name == "SPREAD")
                .order_by(Composite.id, CompositeMember.order)
            ).all()

        legs_by_composite: dict[uuid.UUID, dict[int, uuid.UUID]] = {}
        for composite_id, order, instrument_id in rows:
            legs_by_composite.setdefault(composite_id, {})[order] = instrument_id

        for composite_id, legs in legs_by_composite.items():
            if set(legs.keys()) == {1, 2}:
                OUSpread._composite_legs[composite_id] = (legs[1], legs[2])

        OUSpread._initialised = True

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()

        params_df = self.get_feed(OUParams)
        market_df = self.get_feed(MarketData)
        if params_df.empty or market_df.empty:
            logger.info("Parent frames empty; emitting empty OU_SPREAD frame")
            return pd.DataFrame(columns=["composite_id", "OU_SPREAD"])

        self._ensure_initialised()

        prices_by_instrument: dict[str, float] = {}
        for _, row in market_df.iterrows():
            instrument_id = str(row["instrument_id"])
            close = float(row["CLOSE"])
            if math.isfinite(close) and close > 0:
                prices_by_instrument[instrument_id] = close

        rows: list[dict] = []
        for _, params_row in params_df.iterrows():
            composite_id = uuid.UUID(str(params_row["composite_id"]))
            legs = OUSpread._composite_legs.get(composite_id)
            if legs is None:
                continue
            inst_a, inst_b = legs

            beta = float(params_row["OU_BETA"])
            if not math.isfinite(beta) or beta == 0:
                continue

            price_a = prices_by_instrument.get(str(inst_a))
            price_b = prices_by_instrument.get(str(inst_b))
            if price_a is None or price_b is None:
                continue

            spread = math.log(price_a) - beta * math.log(price_b)
            if not math.isfinite(spread):
                continue

            rows.append(
                {
                    "composite_id": str(composite_id),
                    "OU_SPREAD": round(spread, 8),
                }
            )

        logger.info("Generated OU_SPREAD for %d composites", len(rows))
        return pd.DataFrame(rows, columns=["composite_id", "OU_SPREAD"])


if __name__ == "__main__":
    OUSpread.run()

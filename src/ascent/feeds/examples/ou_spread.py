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

import os
import uuid
from typing import ClassVar

import numpy as np
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

    # Cached leg lookup: one row per composite with stringified UUIDs for
    # both legs. Used as the left side of a vectorized merge with the
    # per-tick params and market data frames.
    _legs_df: ClassVar[pd.DataFrame | None] = None
    _initialised: ClassVar[bool] = False

    _EMPTY_COLUMNS: ClassVar[list[str]] = ["composite_id", "OU_SPREAD"]

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

        composite_ids: list[str] = []
        inst_a: list[str] = []
        inst_b: list[str] = []
        for composite_id, legs in legs_by_composite.items():
            if set(legs.keys()) != {1, 2}:
                continue
            composite_ids.append(str(composite_id))
            inst_a.append(str(legs[1]))
            inst_b.append(str(legs[2]))

        OUSpread._legs_df = pd.DataFrame(
            {"composite_id": composite_ids, "inst_a": inst_a, "inst_b": inst_b}
        )
        OUSpread._initialised = True

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()

        params_df = self.get_feed(OUParams)
        market_df = self.get_feed(MarketData)
        if params_df.empty or market_df.empty:
            logger.info("Parent frames empty; emitting empty OU_SPREAD frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        self._ensure_initialised()
        legs_df = OUSpread._legs_df
        if legs_df is None or legs_df.empty:
            logger.info("No SPREAD composites known; emitting empty OU_SPREAD frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        # Normalize join keys to str without mutating caller frames.
        params = params_df[["composite_id", "OU_BETA"]].assign(
            composite_id=lambda d: d["composite_id"].astype(str),
            OU_BETA=lambda d: d["OU_BETA"].astype(float),
        )
        prices_a = market_df[["instrument_id", "CLOSE"]].rename(
            columns={"instrument_id": "inst_a", "CLOSE": "price_a"}
        )
        prices_a = prices_a.assign(
            inst_a=lambda d: d["inst_a"].astype(str),
            price_a=lambda d: d["price_a"].astype(float),
        )
        prices_b = market_df[["instrument_id", "CLOSE"]].rename(
            columns={"instrument_id": "inst_b", "CLOSE": "price_b"}
        )
        prices_b = prices_b.assign(
            inst_b=lambda d: d["inst_b"].astype(str),
            price_b=lambda d: d["price_b"].astype(float),
        )

        # Vectorized join: composite -> beta -> leg-a price -> leg-b price.
        joined = (
            legs_df.merge(params, on="composite_id", how="inner")
            .merge(prices_a, on="inst_a", how="inner")
            .merge(prices_b, on="inst_b", how="inner")
        )
        if joined.empty:
            logger.info("No composites with both legs priced; emitting empty frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        # Filter degenerate inputs that would produce NaN/inf spreads.
        valid_inputs = (
            (joined["price_a"] > 0)
            & (joined["price_b"] > 0)
            & np.isfinite(joined["price_a"])
            & np.isfinite(joined["price_b"])
            & np.isfinite(joined["OU_BETA"])
            & (joined["OU_BETA"] != 0)
        )
        joined = joined[valid_inputs]
        if joined.empty:
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        spreads = np.log(joined["price_a"].to_numpy()) - joined["OU_BETA"].to_numpy() * np.log(
            joined["price_b"].to_numpy()
        )
        finite = np.isfinite(spreads)

        df = pd.DataFrame(
            {
                "composite_id": joined.loc[finite, "composite_id"].to_numpy(),
                "OU_SPREAD": np.round(spreads[finite], 8),
            }
        )
        logger.info("Generated OU_SPREAD for %d composites", len(df))
        return df


if __name__ == "__main__":
    OUSpread.run()

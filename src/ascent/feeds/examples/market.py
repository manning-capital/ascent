"""Market data feed — per-instrument log-OU OHLCV.

Each instrument that participates in any SPREAD composite gets a single
log-price state that evolves as an Ornstein-Uhlenbeck process around
``log(base_price)``. One CLOSE row is emitted per instrument per tick
regardless of how many composites it appears in, so prices stay consistent
across pairs that share legs (no last-write-wins races when an instrument
sits in many composites).

Because each leg is OU, the realized spread ``ln(p_a) - beta * ln(p_b)`` for
any pair is itself OU with parameters derived in :mod:`ascent.feeds.examples
.ou_params` from the same shared constants — so the entry/exit levels the
strategy reads from :class:`OUParams` describe the same process the spread
actually follows.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import ClassVar

import numpy as np
import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ascent.feeds import Feed
from ascent.feeds.examples._ou_sim import INST_MU, INST_SIGMA, base_price_for
from ascent.feeds.examples.ou_params import OUParams
from ascent.feeds.output import InstrumentAttributes


class MarketData(Feed):
    """Emits OHLCV market data driven by per-instrument log-OU dynamics."""

    class Parameters(BaseModel):
        dt: float = Field(1.0, description="OU time-step per tick (seconds)")

    depends_on = [OUParams]
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_INSTRUMENT"
    display_name = "Market Data"
    description = "Simulated per-instrument log-OU OHLCV market data."

    # Aligned per-instrument arrays sized [n_instruments]. Built once in
    # _ensure_initialised; ``_log_prices`` is mutated in place each tick to
    # advance the OU state for every instrument.
    _instrument_ids: ClassVar[np.ndarray | None] = None
    _log_bases: ClassVar[np.ndarray | None] = None
    _log_prices: ClassVar[np.ndarray | None] = None
    _initialised: ClassVar[bool] = False

    def _ensure_initialised(self) -> None:
        if MarketData._initialised:
            return
        from sqlalchemy import create_engine

        from ascent.database.models.assets import Asset
        from ascent.database.models.composites import Composite, CompositeMember
        from ascent.database.models.instruments import Instrument
        from ascent.database.models.types import CompositeType

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(Instrument.id, Asset.name)
                .distinct()
                .join(CompositeMember, CompositeMember.instrument_id == Instrument.id)
                .join(Composite, CompositeMember.composite_id == Composite.id)
                .join(CompositeType, Composite.composite_type_id == CompositeType.id)
                .join(Asset, Instrument.from_asset_id == Asset.id)
                .where(CompositeType.name == "SPREAD")
            ).all()

            instrument_id_list = [r[0] for r in rows]
            last_close = self._load_last_close_per_instrument(db, instrument_id_list)

        instrument_ids = np.array([str(r[0]) for r in rows], dtype=object)
        log_bases = np.array([math.log(base_price_for(r[1])) for r in rows], dtype=float)

        # Resume per-instrument log-prices from the last persisted CLOSE so the
        # OU walk continues across process restarts. Instruments with no
        # history yet (first run, or never persisted) start at log(base_price).
        log_prices = log_bases.copy()
        for i, inst_id in enumerate(instrument_id_list):
            close = last_close.get(inst_id)
            if close is not None and close > 0:
                log_prices[i] = math.log(close)

        MarketData._instrument_ids = instrument_ids
        MarketData._log_bases = log_bases
        MarketData._log_prices = log_prices
        MarketData._initialised = True

    @staticmethod
    def _load_last_close_per_instrument(
        db: Session, instrument_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, float]:
        """Return ``{instrument_id: latest CLOSE value}`` for the given ids.

        Empty dict if no CLOSE attribute exists yet (pre-first-run) or no rows
        have been persisted for any of these instruments.
        """
        if not instrument_ids:
            return {}

        from ascent.database.models.descriptors import Attribute
        from ascent.database.models.instruments import InstrumentAttribute

        close_attr_id = db.execute(
            select(Attribute.id).where(Attribute.name == "CLOSE")
        ).scalar_one_or_none()
        if close_attr_id is None:
            return {}

        latest = (
            select(
                InstrumentAttribute.instrument_id.label("instrument_id"),
                func.max(InstrumentAttribute.timestamp).label("max_ts"),
            )
            .where(InstrumentAttribute.attribute_id == close_attr_id)
            .where(InstrumentAttribute.instrument_id.in_(instrument_ids))
            .group_by(InstrumentAttribute.instrument_id)
            .subquery()
        )
        rows = db.execute(
            select(
                InstrumentAttribute.instrument_id,
                InstrumentAttribute.attribute_value,
            )
            .join(
                latest,
                and_(
                    InstrumentAttribute.instrument_id == latest.c.instrument_id,
                    InstrumentAttribute.timestamp == latest.c.max_ts,
                ),
            )
            .where(InstrumentAttribute.attribute_id == close_attr_id)
        ).all()
        return {r[0]: float(r[1]) for r in rows}

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        logger = self.get_logger()
        self._ensure_initialised()

        instrument_ids = MarketData._instrument_ids
        if instrument_ids is None or len(instrument_ids) == 0:
            logger.info("No SPREAD-composite instruments in scope; emitting empty frame")
            return pd.DataFrame(columns=["instrument_id", "CLOSE", "VOLUME"])

        dt = self.parameters.dt
        sqrt_dt = math.sqrt(dt)
        n = len(instrument_ids)

        # Vectorized OU step for every instrument simultaneously.
        noise = np.random.standard_normal(n)
        MarketData._log_prices += (
            INST_MU * (MarketData._log_bases - MarketData._log_prices) * dt
            + INST_SIGMA * sqrt_dt * noise
        )

        universe_ids = self.get_universe()
        if not universe_ids:
            logger.info("Universe empty; emitting empty frame")
            return pd.DataFrame(columns=["instrument_id", "CLOSE", "VOLUME"])

        universe_str = {str(u) for u in universe_ids}
        in_universe = np.fromiter(
            (iid in universe_str for iid in instrument_ids), dtype=bool, count=n
        )
        if not in_universe.any():
            logger.info("No emitted instruments in universe; emitting empty frame")
            return pd.DataFrame(columns=["instrument_id", "CLOSE", "VOLUME"])

        emitted_ids = instrument_ids[in_universe]
        prices = np.exp(MarketData._log_prices[in_universe])
        volumes = np.random.uniform(100, 10000, size=emitted_ids.size)

        df = pd.DataFrame(
            {
                "instrument_id": emitted_ids,
                "CLOSE": np.round(prices, 6),
                "VOLUME": np.round(volumes, 2),
            }
        )
        logger.info("Generated market data for %d instrument rows", len(df))
        return df


if __name__ == "__main__":
    MarketData.run()
